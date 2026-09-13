# Process API tests cover persistence, independent review, and evidence-grounded views.

import asyncio
import json
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.routes.bank as bank_routes
import app.services.bank as bank_module
import app.services.processes as processes_module
from app.db.models import LegalProcess
from app.db.session import SessionFactory
from app.main import app
from app.schemas.chat import ProcessDocumentListResponse, ProcessDocumentResponse
from app.schemas.judge import JudgeFinding, JudgeReviewRequest, JudgeReviewResponse
from app.schemas.processes import (
    EvidenceMatrixCitation,
    EvidenceMatrixEntry,
    EvidenceMatrixResponse,
    InferredProcessTitle,
)


@pytest.mark.asyncio
async def test_judge_review_never_exposes_unexpected_failure_as_http_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected_failure(*_: object) -> JudgeReviewResponse:
        raise RuntimeError("unexpected judge failure")

    monkeypatch.setattr(
        bank_routes.bank_dashboard_service,
        "review_decision",
        unexpected_failure,
    )
    transport = ASGITransport(app=app)
    decision_id = uuid.uuid4()
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/v1/bank/decisions/{decision_id}/judge-review")
        stream_response = await client.post(f"/v1/bank/decisions/{decision_id}/judge-review/stream")
    assert response.status_code == 502
    assert response.json()["detail"] == (
        "Não foi possível concluir a revisão independente. Tente novamente."
    )
    assert stream_response.status_code == 200
    payloads = [
        json.loads(line.removeprefix("data: "))
        for line in stream_response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert payloads[0] == {"message": "A revisão independente foi iniciada."}
    assert payloads[1] == {
        "message": "Não foi possível concluir a revisão independente. Tente novamente."
    }


@pytest.mark.asyncio
async def test_evidence_matrix_keeps_only_available_pdf_page_citations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_path = "uploads/matriz/contrato.pdf"

    class MatrixModel:
        def with_structured_output(self, *_: object, **__: object) -> "MatrixModel":
            return self

        async def ainvoke(self, *_: object, **__: object) -> EvidenceMatrixResponse:
            return EvidenceMatrixResponse(
                entries=[
                    EvidenceMatrixEntry(
                        question="Houve contratação?",
                        status="supported",
                        explanation="O contrato identifica a contratação.",
                        citations=[
                            EvidenceMatrixCitation(
                                document_path=document_path,
                                document_name="nome incorreto.pdf",
                                page=3,
                            )
                        ],
                    ),
                    EvidenceMatrixEntry(
                        question="O crédito entrou na conta?",
                        status="contradicted",
                        explanation="A página não demonstra o crédito.",
                        citations=[
                            EvidenceMatrixCitation(
                                document_path=document_path,
                                document_name="nome incorreto.pdf",
                                page=3,
                            )
                        ],
                    ),
                    EvidenceMatrixEntry(
                        question="Os descontos batem?",
                        status="supported",
                        explanation="O documento menciona descontos.",
                    ),
                    EvidenceMatrixEntry(
                        question="A assinatura é compatível?",
                        status="no_evidence",
                        explanation="Sem base suficiente.",
                    ),
                ]
            )

    class MatrixRepository:
        def __init__(self, *_: object) -> None:
            pass

        def read_pdf(self, _: str, **__: object) -> dict[str, object]:
            return {
                "status": "ok",
                "start_page": 1,
                "end_page": 3,
                "content": "--- página 3 --- Contrato.",
            }

    async def list_documents(
        _: object,
        case_number: str,
    ) -> ProcessDocumentListResponse:
        return ProcessDocumentListResponse(
            case_number=case_number,
            documents=[
                ProcessDocumentResponse(
                    id=None,
                    case_number=case_number,
                    path=document_path,
                    original_filename="contrato.pdf",
                    document_type="contract",
                    kind="pdf",
                    source="upload",
                    size_bytes=1,
                    sha256=None,
                    created_at=None,
                )
            ],
        )

    monkeypatch.setattr(processes_module, "ChatOpenAI", lambda **_: MatrixModel())
    monkeypatch.setattr(processes_module, "DocumentRepository", MatrixRepository)
    monkeypatch.setattr(processes_module.process_document_service, "list", list_documents)
    process_id: uuid.UUID | None = None
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            draft_response = await client.post("/v1/processes/drafts")
            assert draft_response.status_code == 201
            draft = draft_response.json()
            process_id = uuid.UUID(draft["id"])

            response = await client.get(f"/v1/processes/{draft['case_number']}/evidence-matrix")
            assert response.status_code == 200
            entries = response.json()["entries"]
            assert entries[0]["status"] == "supported"
            assert entries[0]["citations"] == [
                {
                    "document_path": document_path,
                    "document_name": "contrato.pdf",
                    "page": 3,
                }
            ]
            assert entries[1]["status"] == "contradicted"
            assert entries[1]["citations"][0]["document_name"] == "contrato.pdf"
            assert entries[2]["status"] == "no_evidence"
            assert entries[2]["citations"] == []
            assert entries[3]["status"] == "no_evidence"
        finally:
            if process_id is not None:
                async with SessionFactory() as session:
                    process = await session.get(LegalProcess, process_id)
                    if process is not None:
                        await session.delete(process)
                        await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_process_fields_title_and_submitted_decision_are_persisted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class TitleModel:
        def with_structured_output(self, *_: object, **__: object) -> "TitleModel":
            return self

        async def ainvoke(self, *_: object, **__: object) -> InferredProcessTitle:
            return InferredProcessTitle(title="Fraude Bancária no Amazonas")

    monkeypatch.setattr(processes_module, "ChatOpenAI", lambda **_: TitleModel())
    reviewed_requests: list[JudgeReviewRequest] = []

    async def list_process_documents(
        _: object,
        case_number: str,
    ) -> ProcessDocumentListResponse:
        return ProcessDocumentListResponse(
            case_number=case_number,
            documents=[
                ProcessDocumentResponse(
                    id=None,
                    case_number=case_number,
                    path=f"uploads/{case_number}/autos.pdf",
                    original_filename="autos.pdf",
                    document_type="case_record",
                    kind="pdf",
                    source="upload",
                    size_bytes=1,
                    sha256=None,
                    created_at=None,
                ),
                ProcessDocumentResponse(
                    id=None,
                    case_number=case_number,
                    path=f"uploads/{case_number}/contrato.pdf",
                    original_filename="contrato.pdf",
                    document_type="contract",
                    kind="pdf",
                    source="upload",
                    size_bytes=1,
                    sha256=None,
                    created_at=None,
                ),
            ],
        )

    async def judge_review(_: object, request: JudgeReviewRequest) -> JudgeReviewResponse:
        await asyncio.sleep(0.05)
        reviewed_requests.append(request)
        return JudgeReviewResponse(
            disposition="insufficient_evidence",
            confidence=0.5,
            summary="A documentação disponível é insuficiente para confirmar a decisão.",
            findings=[
                JudgeFinding(
                    issue="Validade da decisão",
                    conclusion="Insuficiência de prova",
                    reasoning=(
                        "Os documentos disponíveis foram lidos, mas não sustentam "
                        "uma conclusão definitiva."
                    ),
                )
            ],
            missing_evidence=["Extrato bancário completo"],
            case_number=request.case_number,
            consulted_documents=[document.path for document in request.documents],
            unreadable_documents=[],
            model="test",
            trace_id=uuid.uuid4(),
            langsmith_project="test",
            tracing_enabled=False,
            ml_analysis=None,
            ml_tool_errors=[],
            model_card_consulted=False,
            strategy=None,
            document_node_reads={},
            process_data=None,
        )

    monkeypatch.setattr(bank_module.process_document_service, "list", list_process_documents)
    monkeypatch.setattr(
        processes_module.process_document_service,
        "list",
        list_process_documents,
    )
    monkeypatch.setattr(bank_module.judge_service, "review", judge_review)
    process_id: uuid.UUID | None = None
    old_case_number: str | None = None
    new_case_number = f"9999999-11.2099.8.04.{str(uuid.uuid4().int)[:4]}"

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            draft_response = await client.post("/v1/processes/drafts")
            assert draft_response.status_code == 201
            draft = draft_response.json()
            process_id = uuid.UUID(draft["id"])
            old_case_number = draft["case_number"]
            assert "location" not in draft
            assert "subject" not in draft

            draft_overview = await client.get(f"/v1/processes/{old_case_number}/financial-overview")
            assert draft_overview.status_code == 200
            draft_overview_body = draft_overview.json()
            assert draft_overview_body["evidence_score"] == pytest.approx(1 / 6)
            assert draft_overview_body["risk"] is None
            assert draft_overview_body["decision"] is None
            assert "location" not in draft_overview_body
            assert "subject" not in draft_overview_body

            draft_decision = await client.post(
                f"/v1/processes/{old_case_number}/decisions",
                json={"recommendation": "defense", "amount": None},
            )
            assert draft_decision.status_code == 201

            sentinel_response = await client.patch(
                f"/v1/processes/{old_case_number}",
                json={
                    "title": "Fraude Bancária",
                    "state": "AM",
                    "sub_subject": "fraud",
                    "claim_amount": 0.01,
                    "evidence": {
                        "contract": True,
                        "bank_statement": True,
                        "credit_proof": True,
                        "dossier": True,
                        "debt_evolution": True,
                        "referenced_report": True,
                    },
                },
            )
            assert sentinel_response.status_code == 200
            sentinel_overview_response = await client.get(
                f"/v1/processes/{old_case_number}/financial-overview"
            )
            assert sentinel_overview_response.status_code == 200
            sentinel_overview = sentinel_overview_response.json()
            assert sentinel_overview["risk"] is None
            assert sentinel_overview["decision"] is None

            updated_response = await client.patch(
                f"/v1/processes/{old_case_number}",
                json={
                    "case_number": new_case_number,
                    "title": "Novo processo",
                    "state": "AM",
                    "sub_subject": "fraud",
                    "claim_amount": 18000,
                    "evidence": {
                        "contract": True,
                        "bank_statement": False,
                        "credit_proof": True,
                        "dossier": False,
                        "debt_evolution": True,
                        "referenced_report": False,
                    },
                },
            )
            assert updated_response.status_code == 200
            updated = updated_response.json()
            assert updated["case_number"] == new_case_number
            assert updated["model_inputs_edited"] is True
            assert updated["claim_amount"] == 18000

            title_response = await client.post(f"/v1/processes/{new_case_number}/infer-title")
            assert title_response.status_code == 200
            assert title_response.json()["title"] == "Fraude Bancária no Amazonas"

            partial_overview_response = await client.get(
                f"/v1/processes/{new_case_number}/financial-overview"
            )
            assert partial_overview_response.status_code == 200
            partial_overview = partial_overview_response.json()
            assert partial_overview["evidence_score"] == 0.5
            assert partial_overview["risk"] is not None
            assert partial_overview["decision"] is not None

            partial_recommendation = partial_overview["decision"]["recommendation"]
            partial_decision = await client.post(
                f"/v1/processes/{new_case_number}/decisions",
                json={
                    "recommendation": partial_recommendation,
                    "amount": (
                        partial_overview["decision"]["agreement_range"]["target"]
                        if partial_recommendation == "agreement"
                        else None
                    ),
                },
            )
            assert partial_decision.status_code == 201

            complete_evidence_response = await client.patch(
                f"/v1/processes/{new_case_number}",
                json={
                    "evidence": {
                        "contract": True,
                        "bank_statement": True,
                        "credit_proof": True,
                        "dossier": True,
                        "debt_evolution": True,
                        "referenced_report": True,
                    }
                },
            )
            assert complete_evidence_response.status_code == 200
            complete_overview_response = await client.get(
                f"/v1/processes/{new_case_number}/financial-overview"
            )
            assert complete_overview_response.status_code == 200
            complete_overview = complete_overview_response.json()
            model_recommendation = complete_overview["decision"]["recommendation"]
            expected_condemnation = complete_overview["risk"]["expected_condemnation"]
            favorable_amount = max(expected_condemnation - 1000, 1)
            divergent_recommendation = (
                "defense" if model_recommendation != "defense" else "human_review"
            )
            unjustified_divergence = await client.post(
                f"/v1/processes/{new_case_number}/decisions",
                json={
                    "recommendation": divergent_recommendation,
                    "amount": None,
                },
            )
            assert unjustified_divergence.status_code == 422

            decision_response = await client.post(
                f"/v1/processes/{new_case_number}/decisions",
                json={
                    "recommendation": "agreement",
                    "amount": favorable_amount,
                    "justification": "Acordo reduz a exposição esperada do processo.",
                },
            )
            assert decision_response.status_code == 201
            decision = decision_response.json()
            assert decision["process_id"] == str(process_id)
            assert decision["recommendation"] == "agreement"
            assert decision["amount"] == favorable_amount
            assert decision["justification"] == "Acordo reduz a exposição esperada do processo."
            assert decision["bank_status"] == "pending"
            assert decision["bank_reviewed_at"] is None
            assert decision["outcome"] == "pending"
            assert decision["actual_cost"] is None
            assert decision["outcome_recorded_at"] is None
            assert decision["negotiation_status"] == "pending"
            assert decision["negotiation_amount"] is None
            assert decision["negotiation_updated_at"] is None

            latest_response = await client.get(f"/v1/processes/{new_case_number}/decisions/latest")
            assert latest_response.status_code == 200
            assert latest_response.json()["id"] == decision["id"]

            bank_dashboard_response = await client.get("/v1/bank/dashboard")
            assert bank_dashboard_response.status_code == 200
            bank_dashboard = bank_dashboard_response.json()
            bank_item = next(
                item for item in bank_dashboard["decisions"] if item["id"] == decision["id"]
            )
            assert bank_item["case_number"] == new_case_number
            assert bank_item["recommendation"] == "agreement"
            assert bank_item["amount"] == favorable_amount
            assert bank_item["justification"] == decision["justification"]
            assert bank_item["bank_status"] == "pending"
            assert bank_item["claim_amount"] == 18000
            assert bank_item["expected_cost"] == pytest.approx(expected_condemnation)
            assert bank_item["outcome"] == "pending"
            assert bank_item["actual_cost"] is None
            assert "model_recommendation" not in bank_item
            assert "adherence_status" not in bank_item
            assert "negotiation_status" not in bank_item

            unapproved_outcome = await client.post(
                f"/v1/bank/decisions/{decision['id']}/outcome",
                json={"outcome": "favorable", "actual_cost": 0},
            )
            assert unapproved_outcome.status_code == 422
            assert unapproved_outcome.json()["detail"] == (
                "Encaminhe a decisão antes de registrar o resultado."
            )

            review_count_before = len(reviewed_requests)
            judge_review_response, duplicate_review_response = await asyncio.gather(
                client.post(f"/v1/bank/decisions/{decision['id']}/judge-review"),
                client.post(f"/v1/bank/decisions/{decision['id']}/judge-review"),
            )
            assert judge_review_response.status_code == 200
            assert duplicate_review_response.status_code == 200
            assert len(reviewed_requests) == review_count_before + 1
            judge_review_body = judge_review_response.json()
            expected_document_paths = [
                f"uploads/{new_case_number}/autos.pdf",
                f"uploads/{new_case_number}/contrato.pdf",
            ]
            assert judge_review_body["consulted_documents"] == expected_document_paths
            assert [document.path for document in reviewed_requests[-1].documents] == (
                expected_document_paths
            )
            assert decision["justification"] in reviewed_requests[-1].question
            assert '"case_context"' in reviewed_requests[-1].question
            judge_review_stream_response = await client.post(
                f"/v1/bank/decisions/{decision['id']}/judge-review/stream"
            )
            assert judge_review_stream_response.status_code == 200
            assert "event: ready" in judge_review_stream_response.text
            assert "event: complete" in judge_review_stream_response.text

            approve_response = await client.post(f"/v1/bank/decisions/{decision['id']}/approve")
            assert approve_response.status_code == 200
            approved = approve_response.json()
            assert approved["bank_status"] == "approved"
            assert approved["bank_reviewed_at"] is not None
            assert approved["outcome"] == "pending"
            assert approved["actual_cost"] is None
            assert approved["outcome_recorded_at"] is None

            refreshed_dashboard_response = await client.get("/v1/bank/dashboard")
            assert refreshed_dashboard_response.status_code == 200
            refreshed_dashboard = refreshed_dashboard_response.json()
            refreshed_item = next(
                item for item in refreshed_dashboard["decisions"] if item["id"] == decision["id"]
            )
            assert refreshed_item["bank_status"] == "approved"
            assert refreshed_item["outcome"] == "pending"
            assert refreshed_item["actual_cost"] is None
            assert refreshed_dashboard["metrics"]["approved_count"] >= 1
            assert refreshed_dashboard["metrics"]["pending_outcome_count"] >= 1
            invalid_outcome_response = await client.post(
                f"/v1/bank/decisions/{decision['id']}/outcome",
                json={"outcome": "settled", "actual_cost": 0},
            )
            assert invalid_outcome_response.status_code == 422

            outcome_response = await client.post(
                f"/v1/bank/decisions/{decision['id']}/outcome",
                json={"outcome": "settled", "actual_cost": favorable_amount},
            )
            assert outcome_response.status_code == 200
            recorded_outcome = outcome_response.json()
            assert recorded_outcome["outcome"] == "settled"
            assert recorded_outcome["actual_cost"] == pytest.approx(favorable_amount)
            assert recorded_outcome["outcome_recorded_at"] is not None

            recorded_dashboard_response = await client.get("/v1/bank/dashboard")
            assert recorded_dashboard_response.status_code == 200
            recorded_dashboard = recorded_dashboard_response.json()
            recorded_item = next(
                item for item in recorded_dashboard["decisions"] if item["id"] == decision["id"]
            )
            assert recorded_item["outcome"] == "settled"
            assert recorded_item["actual_cost"] == pytest.approx(favorable_amount)
            assert recorded_dashboard["metrics"]["outcome_recorded_count"] >= 1
            assert recorded_dashboard["metrics"]["actual_cost_total"] >= favorable_amount
            assert recorded_dashboard["metrics"]["expected_cost_total"] >= expected_condemnation

            overview_response = await client.get(
                f"/v1/processes/{new_case_number}/financial-overview"
            )
            assert overview_response.status_code == 200
            overview = overview_response.json()
            assert overview["input_source"] == "process_registry"
            assert overview["risk"] is not None
            assert overview["decision"] is not None
            assert overview["latest_decision"]["id"] == decision["id"]
        finally:
            if process_id is not None:
                async with SessionFactory() as session:
                    process = await session.get(LegalProcess, process_id)
                    if process is not None:
                        await session.delete(process)
                        await session.commit()
