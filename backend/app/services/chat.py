import asyncio
import hashlib
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from fastapi.sse import ServerSentEvent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import ChatMessage, ChatSession
from app.db.session import SessionFactory
from app.documents import DOCUMENT_TOOLS
from app.graph.chat import build_chat_react_graph
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatMessageResponse,
    ChatSessionResponse,
    ChatStreamRequest,
)
from app.schemas.processes import LegalProcessResponse
from app.services.process_documents import process_document_service
from app.services.processes import legal_process_service

logger = logging.getLogger(__name__)
_STREAM_HEARTBEAT_SECONDS = 12
_STREAM_MAX_SECONDS = 75
_STREAM_END = object()
_DOCUMENT_TOOL_NAMES = {tool.name for tool in DOCUMENT_TOOLS}




@dataclass(frozen=True)
class ChatStreamContext:
    session_id: uuid.UUID
    case_number: str
    trace_id: uuid.UUID
    messages: list[BaseMessage]
    document_paths: list[str]


def _message_chunk_text(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    parts = []
    if isinstance(content, list):
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
    return "".join(parts)


def _tool_result_summary(output: Any) -> dict[str, str]:
    if hasattr(output, "content"):
        output = output.content
    try:
        payload = json.loads(str(output))
    except (TypeError, json.JSONDecodeError):
        return {"status": "error", "document_path": ""}
    if not isinstance(payload, dict):
        return {"status": "error", "document_path": ""}
    return {
        "status": str(payload.get("status", "error")),
        "document_path": str(payload.get("document_path", "")),
    }


@lru_cache
def get_compiled_chat_graph():
    settings = get_settings()
    model = ChatOpenAI(
        model=settings.openai_chat_model,
        api_key=settings.openai_api_key,
        temperature=0,
        streaming=True,
        use_responses_api=True,
        output_version="responses/v1",
        timeout=60,
        max_retries=0,
    )
    agent_model = model.bind_tools(DOCUMENT_TOOLS, parallel_tool_calls=True).with_config(
        {"run_name": "process-chat-react-agent", "tags": ["chat-react-agent"]}
    )
    final_model = model.with_config(
        {"run_name": "process-chat-final-answer", "tags": ["chat-final"]}
    )
    return build_chat_react_graph(agent_model, final_model)


class ChatService:
    @staticmethod
    async def _session(
        session: AsyncSession,
        case_number: str,
        chat_id: uuid.UUID,
    ) -> ChatSession:
        result = await session.execute(
            select(ChatSession).where(
                ChatSession.id == chat_id,
                ChatSession.case_number == case_number,
            )
        )
        chat = result.scalar_one_or_none()
        if chat is None:
            raise LookupError("Chat session was not found for this process")
        return chat

    async def create_session(
        self,
        session: AsyncSession,
        case_number: str,
    ) -> ChatSessionResponse:
        normalized_case = process_document_service._validate_case_number(case_number)
        chat = ChatSession(case_number=normalized_case)
        session.add(chat)
        await session.commit()
        await session.refresh(chat)
        return ChatSessionResponse.model_validate(chat)

    async def list_sessions(
        self,
        session: AsyncSession,
        case_number: str,
    ) -> list[ChatSessionResponse]:
        normalized_case = process_document_service._validate_case_number(case_number)
        result = await session.execute(
            select(ChatSession)
            .where(ChatSession.case_number == normalized_case)
            .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        )
        return [ChatSessionResponse.model_validate(chat) for chat in result.scalars()]

    async def history(
        self,
        session: AsyncSession,
        case_number: str,
        chat_id: uuid.UUID,
    ) -> ChatHistoryResponse:
        normalized_case = process_document_service._validate_case_number(case_number)
        chat = await self._session(session, normalized_case, chat_id)
        result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == chat.id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
        return ChatHistoryResponse(
            session=ChatSessionResponse.model_validate(chat),
            messages=[ChatMessageResponse.model_validate(message) for message in result.scalars()],
        )

    async def prepare_stream(
        self,
        session: AsyncSession,
        case_number: str,
        chat_id: uuid.UUID,
        request: ChatStreamRequest,
    ) -> ChatStreamContext:
        normalized_case = process_document_service._validate_case_number(case_number)
        chat = await self._session(session, normalized_case, chat_id)
        legal_process = await legal_process_service.get_by_case_number(session, normalized_case)
        if legal_process is None:
            raise ValueError("Process context was not found in the database")
        process_context = LegalProcessResponse.model_validate(legal_process).model_dump(mode="json")
        documents = await process_document_service.list(session, legal_process.case_number)
        document_paths = [document.path for document in documents.documents]

        history_result = await session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == chat.id)
            .order_by(ChatMessage.created_at, ChatMessage.id)
        )
        history = list(history_result.scalars())
        messages: list[BaseMessage] = [
            HumanMessage(content=message.content)
            if message.role == "user"
            else AIMessage(content=message.content)
            for message in history
        ]
        clean_message = request.message.strip()
        if document_paths:
            document_list = "\n".join(
                f"- {document.path} [tipo={document.document_type}]"
                for document in documents.documents
            )
            messages.append(
                HumanMessage(
                    content=(
                        f"Processo: {legal_process.case_number}\n"
                        "Contexto persistido e autorizado exclusivamente para este processo:\n"
                        f"{json.dumps(process_context, ensure_ascii=False)}\n"
                        "Documentos autorizados exclusivamente para este processo:\n"
                        f"{document_list}\n\n"
                        f"Pergunta do usuário: {clean_message}"
                    )
                )
            )
        else:
            messages.append(
                HumanMessage(
                    content=(
                        "Este é um novo processo sem informações ou documentos anexados. "
                        f"Pergunta do usuário: {clean_message}"
                    )
                )
            )

        user_message = ChatMessage(
            session_id=chat.id,
            role="user",
            content=clean_message,
            document_paths=[],
            trace_id=None,
        )
        session.add(user_message)
        chat.updated_at = datetime.now(UTC)
        await session.commit()
        return ChatStreamContext(
            session_id=chat.id,
            case_number=normalized_case,
            trace_id=uuid.uuid4(),
            messages=messages,
            document_paths=document_paths,
        )

    async def stream(self, context: ChatStreamContext) -> AsyncIterator[ServerSentEvent]:
        sequence = 0

        def event(name: str, data: dict[str, Any]) -> ServerSentEvent:
            nonlocal sequence
            sequence += 1
            return ServerSentEvent(event=name, id=str(sequence), data=data)

        yield event(
            "ready",
            {
                "chat_id": str(context.session_id),
                "trace_id": str(context.trace_id),
                "document_count": len(context.document_paths),
            },
        )

        queue: asyncio.Queue[dict[str, Any] | BaseException | object] = asyncio.Queue()

        async def produce() -> None:
            settings = get_settings()
            try:
                async with asyncio.timeout(_STREAM_MAX_SECONDS):
                    async for graph_event in get_compiled_chat_graph().astream_events(
                        {
                            "messages": context.messages,
                            "document_root": settings.document_root,
                            "allowed_document_paths": context.document_paths,
                            "agent_turns": 0,
                        },
                        config={
                            "run_id": context.trace_id,
                            "run_name": "process-document-chat",
                            "tags": ["process-chat", settings.environment],
                            "metadata": {
                                "case_reference": hashlib.sha256(
                                    context.case_number.encode()
                                ).hexdigest()[:16],
                                "chat_id": str(context.session_id),
                                "document_count": len(context.document_paths),
                                "model": settings.openai_chat_model,
                            },
                            "recursion_limit": 32,
                        },
                        version="v2",
                    ):
                        await queue.put(graph_event)
            except BaseException as exc:
                await queue.put(exc)
            finally:
                await queue.put(_STREAM_END)

        producer = asyncio.create_task(produce())
        answer_chunks: list[str] = []
        final_answer = ""
        consulted_documents: list[str] = []
        unreadable_documents: list[str] = []
        tool_calls: list[dict[str, str]] = []
        tool_call_indexes: dict[str, int] = {}

        try:
            while True:
                try:
                    item = await asyncio.wait_for(
                        queue.get(),
                        timeout=_STREAM_HEARTBEAT_SECONDS,
                    )
                except TimeoutError:
                    yield ServerSentEvent(comment="keep-alive")
                    continue
                if item is _STREAM_END:
                    break
                if isinstance(item, BaseException):
                    raise item

                event_name = item.get("event")
                run_name = item.get("name")
                tags = set(item.get("tags") or item.get("metadata", {}).get("tags") or [])
                data = item.get("data", {})
                if event_name == "on_tool_start" and run_name in _DOCUMENT_TOOL_NAMES:
                    tool_input = data.get("input", {})
                    document_path = (
                        str(tool_input.get("document_path", ""))
                        if isinstance(tool_input, dict)
                        else ""
                    )
                    call_id = str(item.get("run_id") or f"tool-{len(tool_calls) + 1}")
                    tool_call_indexes[call_id] = len(tool_calls)
                    tool_calls.append(
                        {
                            "id": call_id,
                            "tool": str(run_name),
                            "document_path": document_path,
                            "status": "active",
                        }
                    )
                    yield event(
                        "tool_start",
                        {
                            "id": call_id,
                            "tool": run_name,
                            "document_path": document_path,
                        },
                    )
                elif event_name == "on_tool_end" and run_name in _DOCUMENT_TOOL_NAMES:
                    summary = _tool_result_summary(data.get("output"))
                    call_id = str(item.get("run_id") or "")
                    call_index = tool_call_indexes.get(call_id)
                    if call_index is None:
                        call_index = next(
                            (
                                index
                                for index in range(len(tool_calls) - 1, -1, -1)
                                if tool_calls[index]["tool"] == run_name
                                and tool_calls[index]["status"] == "active"
                            ),
                            None,
                        )
                    if call_index is not None:
                        tool_calls[call_index]["status"] = (
                            "error" if summary["status"] == "error" else "complete"
                        )
                        call_id = tool_calls[call_index]["id"]
                    yield event(
                        "tool_end",
                        {"id": call_id, "tool": run_name, **summary},
                    )
                elif event_name == "on_chat_model_stream" and "chat-final" in tags:
                    text = _message_chunk_text(data.get("chunk"))
                    if text:
                        answer_chunks.append(text)
                        yield event("token", {"text": text})
                elif event_name == "on_chain_end" and run_name == "finalize":
                    output = data.get("output", {})
                    if isinstance(output, dict):
                        final_answer = str(output.get("answer", ""))
                        consulted_documents = list(output.get("consulted_documents", []))
                        unreadable_documents = list(output.get("unreadable_documents", []))

            answer = final_answer.strip() or "".join(answer_chunks).strip()
            if not answer:
                raise ValueError("The process chat completed without an answer")
            if not answer_chunks:
                yield event("token", {"text": answer})

            persisted_tool_calls = [
                {
                    **call,
                    "status": "complete" if call["status"] == "active" else call["status"],
                }
                for call in tool_calls
            ]
            async with SessionFactory() as session:
                chat = await self._session(session, context.case_number, context.session_id)
                assistant_message = ChatMessage(
                    session_id=context.session_id,
                    role="assistant",
                    content=answer,
                    document_paths=consulted_documents,
                    tool_calls=persisted_tool_calls,
                    trace_id=context.trace_id,
                )
                session.add(assistant_message)
                chat.updated_at = datetime.now(UTC)
                await session.commit()
                await session.refresh(assistant_message)
                persisted = ChatMessageResponse.model_validate(assistant_message)
            yield event(
                "complete",
                {
                    "message": persisted.model_dump(mode="json"),
                    "consulted_documents": consulted_documents,
                    "unreadable_documents": unreadable_documents,
                },
            )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            logger.warning(
                "Process document chat timed out",
                extra={"trace_id": str(context.trace_id)},
            )
            yield event(
                "error",
                {
                    "message": "A resposta excedeu o tempo de espera. Tente novamente.",
                    "trace_id": str(context.trace_id),
                },
            )
        except Exception:
            logger.exception(
                "Process document chat failed",
                extra={"trace_id": str(context.trace_id)},
            )
            yield event(
                "error",
                {
                    "message": "The document chat failed",
                    "trace_id": str(context.trace_id),
                },
            )
        finally:
            if not producer.done():
                producer.cancel()
                try:
                    await producer
                except asyncio.CancelledError:
                    pass


chat_service = ChatService()
