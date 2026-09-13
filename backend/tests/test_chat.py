import asyncio
import json
import uuid
from pathlib import Path

import pytest
from fastapi.sse import ServerSentEvent
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

import app.api.routes.chat as chat_routes
import app.services.chat as chat_module
from app.config import get_settings
from app.db.models import Analysis, ChatSession, LegalProcess
from app.db.session import SessionFactory
from app.documents import DocumentRepository
from app.graph.chat import build_chat_react_graph
from app.main import app
from app.schemas.chat import ChatStreamRequest
from app.services.chat import ChatService, ChatStreamContext, chat_service


@pytest.mark.asyncio(loop_scope="session")
async def test_process_documents_and_chat_sessions_are_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = str(uuid.uuid4().int)[:18]
    case_number = f"9999999-99.2099.9.99.{suffix[:4]}"
    other_case = f"8888888-88.2099.9.88.{suffix[-4:]}"
    csv_bytes = b"campo,valor\nvalor_da_causa,12500\n"
    document_id: str | None = None
    chat_id: str | None = None
    missing_upload_directory: Path | None = None

    analysis_refreshes: list[str] = []

    async def refresh_analysis(_: object, refreshed_case_number: str, **__: object) -> None:
        analysis_refreshes.append(refreshed_case_number)

    monkeypatch.setattr(
        chat_routes.analysis_service,
        "refresh_for_process",
        refresh_analysis,
        raising=False,
    )
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

            original_upload_path, _ = DocumentRepository(get_settings().document_root).resolve(
                uploaded["path"], expected_suffixes={".csv"}
            )
            missing_upload_directory = original_upload_path.parent
            original_upload_path.unlink()
            missing_documents = await client.get(f"/v1/processes/{case_number}/documents")
            assert missing_documents.json()["documents"] == []

            duplicate = await client.post(
                f"/v1/processes/{case_number}/documents",
                data={"document_type": "other"},
                files={"file": ("copia.csv", csv_bytes, "text/csv")},
            )
            assert duplicate.status_code == 201
            assert duplicate.json()["id"] == document_id
            assert duplicate.json()["path"] != uploaded["path"]

            process_documents = await client.get(f"/v1/processes/{case_number}/documents")
            other_documents = await client.get(f"/v1/processes/{other_case}/documents")
            assert [item["id"] for item in process_documents.json()["documents"]] == [document_id]
            assert other_documents.json()["documents"] == []

            content = await client.get(
                f"/v1/processes/{case_number}/documents/content",
                params={"document_path": duplicate.json()["path"]},
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
            assert analysis_refreshes == [case_number, case_number]
        finally:
            if document_id is not None:
                await client.delete(f"/v1/processes/{case_number}/documents/{document_id}")
            if missing_upload_directory is not None and missing_upload_directory.exists():
                missing_upload_directory.rmdir()

    if chat_id is not None:
        async with SessionFactory() as session:
            chat = await session.get(ChatSession, uuid.UUID(chat_id))
            if chat is not None:
                await session.delete(chat)
                await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_chat_prompt_refreshes_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    draft_id: uuid.UUID | None = None
    chat_id: uuid.UUID | None = None
    case_number: str | None = None

    analysis_refreshes: list[tuple[str, str, str | None]] = []

    async def refresh_analysis(
        _: object,
        refreshed_case_number: str,
        *,
        analysis_review_mode: str = "standard",
        lawyer_justification: str | None = None,
    ) -> None:
        analysis_refreshes.append(
            (refreshed_case_number, analysis_review_mode, lawyer_justification)
        )

    async def completed_stream(_: ChatStreamContext):
        yield ServerSentEvent(event="complete", data={"message": {}})

    monkeypatch.setattr(
        chat_routes.analysis_service,
        "refresh_for_process",
        refresh_analysis,
        raising=False,
    )
    monkeypatch.setattr(chat_routes.chat_service, "stream", completed_stream)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            draft_response = await client.post("/v1/processes/drafts")
            assert draft_response.status_code == 201
            draft = draft_response.json()
            draft_id = uuid.UUID(draft["id"])
            case_number = draft["case_number"]

            session_response = await client.post(f"/v1/processes/{case_number}/chats")
            assert session_response.status_code == 201
            chat_id = uuid.UUID(session_response.json()["id"])

            response = await client.post(
                f"/v1/processes/{case_number}/chats/{chat_id}/messages/stream",
                json={"message": "Quais documentos ainda preciso anexar?"},
            )
            assert response.status_code == 200

            manual_review_response = await client.post(
                f"/v1/processes/{case_number}/chats/{chat_id}/messages/stream",
                json={
                    "message": "A defesa é adequada porque o crédito foi comprovado.",
                    "analysis_review_mode": "agreement_justification",
                },
            )
            assert manual_review_response.status_code == 200

            inferred_review_response = await client.post(
                f"/v1/processes/{case_number}/chats/{chat_id}/messages/stream",
                json={
                    "message": "Revise a justificativa de acordo diante do contrato disponível.",
                },
            )
            assert inferred_review_response.status_code == 200
            assert analysis_refreshes == [
                (case_number, "standard", None),
                (
                    case_number,
                    "agreement_justification",
                    "A defesa é adequada porque o crédito foi comprovado.",
                ),
                (
                    case_number,
                    "agreement_justification",
                    "Revise a justificativa de acordo diante do contrato disponível.",
                ),
            ]
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


@pytest.mark.asyncio(loop_scope="session")
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


@pytest.mark.asyncio(loop_scope="session")
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
async def test_chat_with_documents_keeps_greeting_as_latest_user_message() -> None:
    agent_calls = 0
    finalizer_messages: list[object] = []

    async def greeting_agent(_: object) -> AIMessage:
        nonlocal agent_calls
        agent_calls += 1
        return AIMessage(content="Olá! Como posso ajudar?")

    async def greeting_finalizer(messages: object) -> AIMessage:
        assert isinstance(messages, list)
        finalizer_messages.extend(messages)
        return AIMessage(content="Olá! Como posso ajudar?")

    graph = build_chat_react_graph(
        RunnableLambda(greeting_agent),
        RunnableLambda(greeting_finalizer),
    )
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="olaa")],
            "allowed_document_paths": ["cases/autos.pdf"],
            "agent_turns": 0,
        }
    )

    user_messages = [message for message in finalizer_messages if isinstance(message, HumanMessage)]
    assert agent_calls == 1
    assert isinstance(finalizer_messages[0], SystemMessage)
    assert "consultados=" not in str(finalizer_messages[0].content)
    assert "falhas_de_leitura=" not in str(finalizer_messages[0].content)
    assert [message.content for message in user_messages] == ["olaa"]
    assert result["answer"] == "Olá! Como posso ajudar?"
    assert result["consulted_documents"] == []


@pytest.mark.asyncio
async def test_chat_normalizes_friendly_page_references_into_link_citations() -> None:
    document_path = "uploads/laudo/04_Laudo_Referenciado.pdf"

    async def completed_agent(_: object) -> AIMessage:
        return AIMessage(content="Consulta documental concluída.")

    async def friendly_finalizer(_: object) -> AIMessage:
        return AIMessage(
            content=(
                "4) Laudo referenciado\n"
                "p. 1–2\n"
                "- Página 2: apenas complementa com texto institucional."
            )
        )

    graph = build_chat_react_graph(
        RunnableLambda(completed_agent),
        RunnableLambda(friendly_finalizer),
    )
    result = await graph.ainvoke(
        {
            "messages": [
                HumanMessage(content="Resuma o laudo."),
                ToolMessage(
                    content=json.dumps(
                        {
                            "status": "ok",
                            "document_path": document_path,
                            "total_pages": 2,
                            "content": "Conteúdo consultado.",
                        }
                    ),
                    name="read_pdf_document",
                    tool_call_id="read-laudo",
                ),
            ],
            "allowed_document_paths": [document_path],
            "agent_turns": 0,
        }
    )

    assert result["answer"] == (
        "4) Laudo referenciado\n"
        f"[{document_path} — p. 1–2]\n"
        f"- Página 2: apenas complementa com texto institucional. "
        f"[{document_path} — p. 2]"
    )


@pytest.mark.asyncio
async def test_chat_prompts_explain_all_document_gaps_before_a_decision() -> None:
    agent_messages: list[object] = []
    finalizer_messages: list[object] = []

    async def decision_agent(messages: object) -> AIMessage:
        assert isinstance(messages, list)
        agent_messages.extend(messages)
        return AIMessage(content="Não há base suficiente para concluir.")

    async def decision_finalizer(messages: object) -> AIMessage:
        assert isinstance(messages, list)
        finalizer_messages.extend(messages)
        return AIMessage(content="Resposta final.")

    graph = build_chat_react_graph(
        RunnableLambda(decision_agent),
        RunnableLambda(decision_finalizer),
    )
    await graph.ainvoke(
        {
            "messages": [HumanMessage(content="O que falta para tomar uma decisão?")],
            "allowed_document_paths": ["uploads/comprovante-de-credito.pdf"],
            "agent_turns": 0,
        }
    )

    document_categories = (
        "Autos do processo",
        "Contrato",
        "Extrato bancário",
        "Comprovante de crédito",
        "Dossiê de autenticidade",
        "Evolução da dívida",
        "Laudo referenciado",
    )
    for messages in (agent_messages, finalizer_messages):
        assert isinstance(messages[0], SystemMessage)
        prompt = str(messages[0].content)
        assert all(category in prompt for category in document_categories)
        assert "isoladamente não comprova contratação ou anuência" in prompt

    final_prompt = str(finalizer_messages[0].content)
    assert "estado de cada uma das sete categorias documentais" in final_prompt
    assert "presente e útil, ausente, ou autorizada mas não lida/ilegível" in final_prompt
    assert "recomendar acordo, defesa ou revisão humana" in final_prompt


@pytest.mark.asyncio(loop_scope="session")
async def test_chat_persists_completed_document_tool_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DocumentGraph:
        async def astream_events(self, *_: object, **__: object):
            tool_run_id = str(uuid.uuid4())
            yield {
                "event": "on_tool_start",
                "name": "read_pdf_document",
                "run_id": tool_run_id,
                "data": {"input": {"document_path": "cases/evidence.pdf"}},
            }
            yield {
                "event": "on_tool_end",
                "name": "read_pdf_document",
                "run_id": tool_run_id,
                "data": {"output": '{"status":"ok","document_path":"cases/evidence.pdf"}'},
            }
            yield {
                "event": "on_chain_end",
                "name": "finalize",
                "data": {
                    "output": {
                        "answer": "O documento confirma a informação relevante.",
                        "consulted_documents": ["cases/evidence.pdf"],
                        "unreadable_documents": [],
                    }
                },
            }

    monkeypatch.setattr(chat_module, "get_compiled_chat_graph", lambda: DocumentGraph())
    draft_id: uuid.UUID | None = None
    chat_id: uuid.UUID | None = None
    case_number: str | None = None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            draft_response = await client.post("/v1/processes/drafts")
            draft = draft_response.json()
            draft_id = uuid.UUID(draft["id"])
            case_number = draft["case_number"]
            chat_response = await client.post(f"/v1/processes/{case_number}/chats")
            chat_id = uuid.UUID(chat_response.json()["id"])

            async with SessionFactory() as session:
                context = await chat_service.prepare_stream(
                    session,
                    case_number,
                    chat_id,
                    ChatStreamRequest(message="O que consta no documento?"),
                )
            events = [event async for event in chat_service.stream(context)]

            tool_starts = [event for event in events if event.event == "tool_start"]
            tool_ends = [event for event in events if event.event == "tool_end"]
            assert tool_starts[0].data["id"] == tool_ends[0].data["id"]
            assert tool_ends[0].data["status"] == "ok"
            completed = next(event for event in events if event.event == "complete")
            assert completed.data["message"]["tool_calls"] == [
                {
                    "id": tool_starts[0].data["id"],
                    "tool": "read_pdf_document",
                    "document_path": "cases/evidence.pdf",
                    "status": "complete",
                }
            ]

            history = await client.get(f"/v1/processes/{case_number}/chats/{chat_id}")
            assert history.status_code == 200
            assert (
                history.json()["messages"][-1]["tool_calls"]
                == completed.data["message"]["tool_calls"]
            )
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


@pytest.mark.asyncio(loop_scope="session")
async def test_latest_analysis_returns_the_persisted_case_analysis() -> None:
    case_number = f"RASCUNHO-{uuid.uuid4()}"
    analysis_id: uuid.UUID | None = None

    try:
        async with SessionFactory() as session:
            analysis = Analysis(
                case_number=case_number,
                status="failed",
                request_payload={
                    "case_number": case_number,
                    "state": "SP",
                    "sub_subject": "generic",
                    "claim_amount": 1_000,
                    "evidence": {
                        "contract": False,
                        "bank_statement": False,
                        "credit_proof": False,
                        "dossier": False,
                        "debt_evolution": False,
                        "referenced_report": False,
                    },
                    "documents": [],
                },
                result_payload=None,
                error_message="analysis failed",
            )
            session.add(analysis)
            await session.commit()
            await session.refresh(analysis)
            analysis_id = analysis.id

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/analyses/latest", params={"case_number": case_number})

        assert response.status_code == 200
        assert response.json()["id"] == str(analysis_id)
        assert response.json()["case_number"] == case_number
        assert response.json()["error_message"] == "analysis failed"
    finally:
        if analysis_id is not None:
            async with SessionFactory() as session:
                analysis = await session.get(Analysis, analysis_id)
                if analysis is not None:
                    await session.delete(analysis)
                    await session.commit()


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
