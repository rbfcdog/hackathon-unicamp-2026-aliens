import json

import pytest

import app.graph.nodes as nodes_module
from app.graph.nodes import ExplanationOutput, explain_recommendation
from app.schemas.analysis import DecisionJustifications


@pytest.mark.asyncio(loop_scope="session")
async def test_explanation_generates_an_editable_rationale_for_every_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received_payload: dict[str, object] = {}

    class ExplanationModel:
        async def ainvoke(self, messages: list[object]) -> ExplanationOutput:
            received_payload.update(json.loads(messages[-1].content))
            return ExplanationOutput(
                explanation="A documentação e a exposição indicam a conduta recomendada.",
                decision_justifications=DecisionJustifications(
                    agreement=(
                        "O acordo pode reduzir a exposição dentro da faixa econômica indicada."
                    ),
                    defense="A defesa é adequada enquanto os documentos sustentarem a contratação.",
                    human_review=(
                        "A revisão humana é necessária para confirmar as lacunas documentais."
                    ),
                ),
            )

    class ExplanationFactory:
        def with_structured_output(self, *_: object, **__: object) -> ExplanationModel:
            return ExplanationModel()

    monkeypatch.setattr(nodes_module, "ChatOpenAI", lambda **_: ExplanationFactory())

    result = await explain_recommendation(
        {
            "model_inputs": {"state": "MA", "sub_subject": "fraud"},
            "document_context": "Contrato e extrato disponíveis.",
            "consulted_documents": ["uploads/contrato.pdf"],
            "unreadable_documents": [],
            "recommendation": "defense",
            "evidence_score": 0.8,
            "loss_probability": 0.2,
            "expected_condemnation": 12000,
            "condemnation_q10": 9000,
            "condemnation_q50": 12000,
            "condemnation_q90": 15000,
            "expected_defense_cost": 3000,
            "risk_band": "low",
            "evaluated_agreement_cost": None,
            "agreement_cheaper": None,
            "next_action": "prepare_defense",
            "human_review_reason": None,
            "agreement_range": None,
            "factors_for_agreement": [],
            "factors_for_defense": ["documentação consistente"],
            "policy_version": "v1",
        }
    )

    assert received_payload["recommendation"] == "defense"
    assert result["explanation"].startswith("A documentação")
    assert result["decision_justifications"] == {
        "agreement": "O acordo pode reduzir a exposição dentro da faixa econômica indicada.",
        "defense": "A defesa é adequada enquanto os documentos sustentarem a contratação.",
        "human_review": "A revisão humana é necessária para confirmar as lacunas documentais.",
    }
