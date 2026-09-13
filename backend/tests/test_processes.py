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
from app.schemas.processes import InferredProcessTitle


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
        stream_response = await client.post(
            f"/v1/bank/decisions/{decision_id}/judge-review/stream"
        )
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
            historical_ratio = 0.6223546701502286
            historical_condemnation = round(18000 * historical_ratio, 2)
            favorable_amount = max(
                min(expected_condemnation, historical_condemnation) - 1000,
                1,
            )
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
            assert decision["model_snapshot"]["case_number"] == new_case_number
            assert "latest_decision" not in decision["model_snapshot"]
            assert decision["justification"] == "Acordo reduz a exposição esperada do processo."
            assert decision["bank_status"] == "pending"
            assert decision["bank_reviewed_at"] is None
            assert decision["projected_outcome"] is None
            assert decision["projected_outcome_reason"] is None

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
            assert bank_item["lawyer_recommendation"] == "agreement"
            assert bank_item["lawyer_amount"] == favorable_amount
            assert bank_item["justification"] == decision["justification"]
            assert bank_item["bank_status"] == "pending"
            assert bank_item["claim_amount"] == 18000
            assert bank_item["historical_estimated_condemnation"] == pytest.approx(
                historical_condemnation
            )
            assert bank_item["projected_decision_cost"] is None
            assert bank_item["optimized_savings"] is None

            judge_review_response = await client.post(
                f"/v1/bank/decisions/{decision['id']}/judge-review"
            )
            assert judge_review_response.status_code == 200
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
            assert '"model_reasoning"' in reviewed_requests[-1].question
            judge_review_stream_response = await client.post(
                f"/v1/bank/decisions/{decision['id']}/judge-review/stream"
            )
            assert judge_review_stream_response.status_code == 200
            assert "event: ready" in judge_review_stream_response.text
            assert "event: complete" in judge_review_stream_response.text

            approve_response = await client.post(
                f"/v1/bank/decisions/{decision['id']}/approve"
            )
            assert approve_response.status_code == 200
            assert approve_response.json()["bank_status"] == "approved"
            assert approve_response.json()["bank_reviewed_at"] is not None
            assert approve_response.json()["projected_outcome"] == "favorable"
            assert "abaixo da exposição estimada" in approve_response.json()[
                "projected_outcome_reason"
            ]
            assert approve_response.json()["projected_decision_cost"] == pytest.approx(
                favorable_amount
            )
            assert approve_response.json()["optimized_savings"] == pytest.approx(
                historical_condemnation - favorable_amount
            )

            refreshed_dashboard_response = await client.get("/v1/bank/dashboard")
            assert refreshed_dashboard_response.status_code == 200
            refreshed_dashboard = refreshed_dashboard_response.json()
            refreshed_item = next(
                item
                for item in refreshed_dashboard["decisions"]
                if item["id"] == decision["id"]
            )
            assert refreshed_item["bank_status"] == "approved"
            assert refreshed_dashboard["metrics"]["approved_count"] >= 1
            assert refreshed_item["projected_outcome"] == "favorable"
            assert refreshed_dashboard["metrics"]["favorable_count"] >= 1
            assert refreshed_dashboard["metrics"]["projected_success_rate"] > 0
            assert refreshed_dashboard["monthly_effectiveness"]
            assert refreshed_dashboard["metrics"][
                "historical_condemnation_ratio"
            ] == pytest.approx(historical_ratio)
            assert refreshed_dashboard["metrics"]["historical_sample_size"] == 12248

            unfavorable_amount = max(
                expected_condemnation,
                historical_condemnation,
            ) + 1000
            unfavorable_response = await client.post(
                f"/v1/processes/{new_case_number}/decisions",
                json={
                    "recommendation": "agreement",
                    "amount": unfavorable_amount,
                    "justification": "Validação do caminho financeiro desfavorável.",
                },
            )
            assert unfavorable_response.status_code == 201
            unfavorable_decision = unfavorable_response.json()
            unfavorable_approval = await client.post(
                f"/v1/bank/decisions/{unfavorable_decision['id']}/approve"
            )
            assert unfavorable_approval.status_code == 200
            assert unfavorable_approval.json()["projected_outcome"] == "unfavorable"
            assert "excede a exposição estimada" in unfavorable_approval.json()[
                "projected_outcome_reason"
            ]

            unfavorable_dashboard_response = await client.get("/v1/bank/dashboard")
            assert unfavorable_dashboard_response.status_code == 200
            unfavorable_dashboard = unfavorable_dashboard_response.json()
            latest_bank_item = next(
                item
                for item in unfavorable_dashboard["decisions"]
                if item["id"] == unfavorable_decision["id"]
            )
            assert latest_bank_item["projected_outcome"] == "unfavorable"
            assert unfavorable_dashboard["metrics"]["unfavorable_count"] >= 1
            assert latest_bank_item["projected_decision_cost"] == pytest.approx(
                unfavorable_amount
            )
            assert latest_bank_item["optimized_savings"] == pytest.approx(
                historical_condemnation - unfavorable_amount
            )

            defense_response = await client.post(
                f"/v1/processes/{new_case_number}/decisions",
                json={
                    "recommendation": "defense",
                    "amount": None,
                    "justification": "A probabilidade de êxito sustenta a defesa.",
                },
            )
            assert defense_response.status_code == 201
            defense_decision = defense_response.json()
            defense_approval = await client.post(
                f"/v1/bank/decisions/{defense_decision['id']}/approve"
            )
            assert defense_approval.status_code == 200
            expected_defense_outcome = (
                "favorable"
                if complete_overview["risk"]["loss_probability"] < 0.5
                else "unfavorable"
            )
            assert (
                defense_approval.json()["projected_outcome"]
                == expected_defense_outcome
            )
            expected_defense_savings = (
                historical_condemnation
                if expected_defense_outcome == "favorable"
                else 0
            )
            assert defense_approval.json()["optimized_savings"] == pytest.approx(
                expected_defense_savings
            )

            overview_response = await client.get(
                f"/v1/processes/{new_case_number}/financial-overview"
            )
            assert overview_response.status_code == 200
            overview = overview_response.json()
            assert overview["input_source"] == "process_registry"
            assert overview["risk"] is not None
            assert overview["decision"] is not None
            assert overview["latest_decision"]["id"] == defense_decision["id"]
        finally:
            if process_id is not None:
                async with SessionFactory() as session:
                    process = await session.get(LegalProcess, process_id)
                    if process is not None:
                        await session.delete(process)
                        await session.commit()
