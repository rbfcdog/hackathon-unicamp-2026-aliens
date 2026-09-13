from typing import Any, Literal, TypedDict


class AnalysisState(TypedDict, total=False):
    request: dict[str, Any]
    model_inputs: dict[str, Any]
    document_context: str
    consulted_documents: list[str]
    unreadable_documents: list[str]
    evidence_score: float
    loss_probability: float
    expected_condemnation: float | None
    condemnation_q10: float | None
    condemnation_q50: float | None
    condemnation_q90: float | None
    model_disagreement: float
    component_probabilities: dict[str, float]
    ensemble_weights: dict[str, float]
    requires_model_review: bool
    model_version: str
    expected_defense_cost: float | None
    risk_band: Literal["low", "medium", "high"]
    evaluated_agreement_cost: float | None
    agreement_cheaper: bool | None
    recommendation: Literal["agreement", "defense", "human_review"]
    agreement_range: dict[str, float] | None
    next_action: Literal["propose_agreement", "prepare_defense", "human_review"]
    human_review_reason: str | None
    factors_for_agreement: list[str]
    factors_for_defense: list[str]
    explanation: str
    decision_justifications: dict[str, str]
    policy_version: str
    agreement_justification_review: dict[str, Any] | None
