import asyncio
import uuid

import app.services.chat as chat_module

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from app.db.models import ChatSession, LegalProcess
from app.db.session import SessionFactory
from app.graph.chat import build_chat_react_graph
from app.main import app
from app.schemas.chat import ChatStreamRequest
from app.services.chat import ChatService, ChatStreamContext, chat_service


@pytest.mark.asyncio(loop_scope="module")
async def test_process_documents_and_chat_sessions_are_isolated() -> None:
    suffix = str(uuid.uuid4().int)[:18]
    case_number = f"9999999-99.2099.9.99.{suffix[:4]}"
    other_case = f"8888888-88.2099.9.88.{suffix[-4:]}"
    csv_bytes = b"campo,valor\nvalor_da_causa,12500\n"
    document_id: str | None = None
    chat_id: str | None = None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            upload = await client.post(
                f"/v1/processes/{case_number}/documents",
                data={"document_type": "other"},
                files={"file": ("dados.csv", csv_bytes, "text/csv")},
            )
            assert upload.status_code == 201
            uploaded = upload.json()
            document_id = uploaded["id"]
            assert uploaded["case_number"] == case_number
            assert uploaded["source"] == "upload"

            duplicate = await client.post(
                f"/v1/processes/{case_number}/documents",
                data={"document_type": "other"},
                files={"file": ("copia.csv", csv_bytes, "text/csv")},
            )
            assert duplicate.status_code == 201
            assert duplicate.json()["id"] == document_id

            process_documents = await client.get(f"/v1/processes/{case_number}/documents")
            other_documents = await client.get(f"/v1/processes/{other_case}/documents")
            assert [item["id"] for item in process_documents.json()["documents"]] == [document_id]
            assert other_documents.json()["documents"] == []

            content = await client.get(
                f"/v1/processes/{case_number}/documents/content",
                params={"document_path": uploaded["path"]},
            )
            cross_process_content = await client.get(
                f"/v1/processes/{other_case}/documents/content",
                params={"document_path": uploaded["path"]},
            )
            assert content.status_code == 200
            assert content.headers["content-type"].startswith("text/csv")
            assert content.content == csv_bytes
            assert cross_process_content.status_code == 404

            created_chat = await client.post(f"/v1/processes/{case_number}/chats")
            assert created_chat.status_code == 201
            chat_id = created_chat.json()["id"]

            history = await client.get(f"/v1/processes/{case_number}/chats/{chat_id}")
            cross_process_history = await client.get(f"/v1/processes/{other_case}/chats/{chat_id}")
            assert history.status_code == 200
            assert history.json()["messages"] == []
            assert cross_process_history.status_code == 404
        finally:
            if document_id is not None:
                await client.delete(f"/v1/processes/{case_number}/documents/{document_id}")

    if chat_id is not None:
        async with SessionFactory() as session:
            chat = await session.get(ChatSession, uuid.UUID(chat_id))
            if chat is not None:
                await session.delete(chat)
                await session.commit()


@pytest.mark.asyncio(loop_scope="module")
async def test_draft_process_allows_a_documentless_chat() -> None:
    draft_id: uuid.UUID | None = None
    chat_id: uuid.UUID | None = None
    case_number: str | None = None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            draft_response = await client.post("/v1/processes/drafts")
            assert draft_response.status_code == 201
            draft = draft_response.json()
            draft_id = uuid.UUID(draft["id"])
            case_number = draft["case_number"]
            assert draft["is_draft"] is True
            assert draft["title"] == "Novo processo"

            documents_response = await client.get(f"/v1/processes/{case_number}/documents")
            assert documents_response.status_code == 200
            assert documents_response.json()["documents"] == []

            session_response = await client.post(f"/v1/processes/{case_number}/chats")
            assert session_response.status_code == 201
            chat_id = uuid.UUID(session_response.json()["id"])

            async with SessionFactory() as session:
                context = await chat_service.prepare_stream(
                    session,
                    case_number,
                    chat_id,
                    ChatStreamRequest(message="Quais informações você precisa?"),
                )
            assert context.document_paths == []
            assert "novo processo sem informações" in str(context.messages[-1].content).lower()
        finally:
            async with SessionFactory() as session:
                if chat_id is not None:
                    chat = await session.get(ChatSession, chat_id)
                    if chat is not None:
                        await session.delete(chat)
                if draft_id is not None:
                    draft_process = await session.get(LegalProcess, draft_id)
                    if draft_process is not None:
                        await session.delete(draft_process)
                await session.commit()


@pytest.mark.asyncio(loop_scope="module")
async def test_documentless_chat_skips_the_document_agent() -> None:
    async def unexpected_agent(_: object) -> AIMessage:
        raise AssertionError("The document agent must not run without documents")

    async def draft_finalizer(_: object) -> AIMessage:
        return AIMessage(content="Conte o que aconteceu e anexe os documentos disponíveis.")

    graph = build_chat_react_graph(
        RunnableLambda(unexpected_agent),
        RunnableLambda(draft_finalizer),
    )
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="Como começo?")],
            "allowed_document_paths": [],
            "agent_turns": 0,
        }
    )

    assert result["answer"] == "Conte o que aconteceu e anexe os documentos disponíveis."
    assert result["consulted_documents"] == []


@pytest.mark.asyncio
async def test_chat_stream_reports_a_timeout_instead_of_waiting_indefinitely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StalledGraph:
        async def astream_events(self, *_: object, **__: object):
            await asyncio.Event().wait()
            yield {}

    monkeypatch.setattr(chat_module, "_STREAM_MAX_SECONDS", 0.01)
    monkeypatch.setattr(chat_module, "get_compiled_chat_graph", lambda: StalledGraph())

    context = ChatStreamContext(
        session_id=uuid.uuid4(),
        case_number="RASCUNHO-00000000000000000000",
        trace_id=uuid.uuid4(),
        messages=[],
        document_paths=[],
    )
    events = [event async for event in ChatService().stream(context)]

    assert [event.event for event in events] == ["ready", "error"]
    assert events[-1].data == {
        "message": "A resposta excedeu o tempo de espera. Tente novamente.",
        "trace_id": str(context.trace_id),
    }
