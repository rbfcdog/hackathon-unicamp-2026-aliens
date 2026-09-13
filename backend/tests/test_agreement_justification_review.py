import json

import pytest
from pydantic import ValidationError

import app.graph.nodes as nodes_module
from app.graph.nodes import review_agreement_justification
from app.schemas.analysis import AnalysisRequest, EvidenceInput


@pytest.mark.asyncio(loop_scope="session")
async def test_review_confronts_justification_with_all_available_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received_payload: dict[str, object] = {}

    class ReviewModel:
        def with_structured_output(self, *_: object, **__: object) -> "ReviewModel":
            return self

        async def ainvoke(self, messages: list[object]) -> dict[str, object]:
            received_payload.update(json.loads(str(messages[-1].content)))
            return {
                "verdict": "partially_supported",
                "summary": "O contrato sustenta a operação, mas o crédito não foi confirmado.",
                "supporting_evidence": ["O contrato anexado identifica a operação discutida."],
                "missing_documents": ["comprovante de crédito"],
            }

    monkeypatch.setattr(nodes_module, "ChatOpenAI", lambda **_: ReviewModel())
    request = AnalysisRequest(
        case_number="0801234-56.2024.8.10.0001",
        state="MA",
        claim_amount=5_000,
        evidence=EvidenceInput(contract=True),
        analysis_review_mode="agreement_justification",
        lawyer_justification="A defesa é adequada porque o contrato identifica a operação.",
    )

    result = await review_agreement_justification(
        {
            "request": request.model_dump(mode="json"),
            "model_inputs": {
                "state": "MA",
                "sub_subject": "generic",
                "claim_amount": 5_000,
                "evidence": {"contract": True},
                "input_source": "request_fields",
                "document_summary": "Contrato identifica a operação.",
            },
            "document_context": "Contrato 123 identifica a operação.",
            "consulted_documents": ["uploads/contrato.pdf", "uploads/extrato.pdf"],
            "explanation": "A análise requer confirmação do crédito.",
            "recommendation": "defense",
        }
    )

    assert received_payload["documentos_consultados"] == [
        "uploads/contrato.pdf",
        "uploads/extrato.pdf",
    ]
    assert result["agreement_justification_review"]["verdict"] == "partially_supported"


@pytest.mark.asyncio(loop_scope="session")
async def test_review_marks_absent_readable_documents_as_insufficient() -> None:
    request = AnalysisRequest(
        case_number="0801234-56.2024.8.10.0001",
        state="MA",
        claim_amount=5_000,
        evidence=EvidenceInput(),
        analysis_review_mode="agreement_justification",
        lawyer_justification="A defesa é adequada.",
    )

    result = await review_agreement_justification(
        {
            "request": request.model_dump(mode="json"),
            "model_inputs": {
                "state": "MA",
                "sub_subject": "generic",
                "claim_amount": 5_000,
                "evidence": {},
                "input_source": "request_fields",
                "document_summary": "",
            },
            "document_context": "",
            "explanation": "Ainda não há base documental.",
            "recommendation": "human_review",
        }
    )

    review = result["agreement_justification_review"]
    assert review["verdict"] == "insufficient_evidence"
    assert review["supporting_evidence"] == []
    assert "contrato" in review["missing_documents"]


def test_review_mode_requires_a_lawyer_justification() -> None:
    with pytest.raises(ValidationError, match="lawyer_justification"):
        AnalysisRequest(
            case_number="0801234-56.2024.8.10.0001",
            state="MA",
            claim_amount=5_000,
            evidence=EvidenceInput(),
            analysis_review_mode="agreement_justification",
        )
