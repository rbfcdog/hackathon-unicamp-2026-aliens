import json
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import tool

from app.config import get_settings
from app.ml.risk import TrainedRiskModel
from app.schemas.analysis import EvidenceInput


@lru_cache(maxsize=4)
def _load_risk_model(artifact_path: str) -> TrainedRiskModel:
    return TrainedRiskModel(artifact_path)


def _resolve_backend_path(path_value: str) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[2] / path
    return path.resolve()


def _json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def estimate_case_risk_payload(
    *,
    uf: str,
    sub_subject: Literal["fraud", "generic"],
    claim_amount: float,
    evidence: EvidenceInput,
    input_source: str,
    evidence_document_paths: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    try:
        state = uf.strip().upper()
        if len(state) != 2:
            raise ValueError("uf must contain exactly two letters")
        if claim_amount <= 0:
            raise ValueError("claim_amount must be positive")
        settings = get_settings()
        estimate = _load_risk_model(settings.model_artifact_path).predict(
            state=state,
            sub_subject=sub_subject,
            evidence=evidence,
            claim_amount=claim_amount,
        )
        return {
            "status": "ok",
            "tool": "estimate_case_risk",
            "input_source": input_source,
            "inputs": {
                "uf": state,
                "sub_subject": sub_subject,
                "claim_amount": claim_amount,
                "claim_amount_usage": "severity_only",
                "input_source": input_source,
                "evidence_document_paths": evidence_document_paths or {},
                "evidence": evidence.model_dump(mode="json"),
            },
            "estimate": asdict(estimate),
            "limitations": [
                "The estimate is statistical and does not establish any fact in evidence.",
                "Document-presence flags are associations, not causal effects.",
                (
                    "The pre-judgment claim amount is used only by the severity model; "
                    "it does not affect adverse-result probability."
                ),
                ("Paid, awarded, settled, and other post-outcome amounts are never model inputs."),
                (
                    "The model was trained on the synthetic hackathon dataset and needs "
                    "external validation."
                ),
                "The lawyer must verify every model input against the referenced sources.",
            ],
        }
    except Exception as exc:
        return {
            "status": "error",
            "tool": "estimate_case_risk",
            "error": str(exc),
        }


@tool
def estimate_case_risk(
    uf: str,
    sub_subject: Literal["fraud", "generic"],
    claim_amount: float,
    contract: bool,
    bank_statement: bool,
    credit_proof: bool,
    dossier: bool,
    debt_evolution: bool,
    referenced_report: bool,
) -> str:
    """Estimate adverse-result risk and condemnation range from verified structured facts."""
    evidence = EvidenceInput(
        contract=contract,
        bank_statement=bank_statement,
        credit_proof=credit_proof,
        dossier=dossier,
        debt_evolution=debt_evolution,
        referenced_report=referenced_report,
    )
    return _json(
        estimate_case_risk_payload(
            uf=uf,
            sub_subject=sub_subject,
            claim_amount=claim_amount,
            evidence=evidence,
            input_source="facts supplied explicitly to the ML tool",
        )
    )


@tool
def inspect_risk_model_card() -> str:
    """Return validation metrics, important features, ensemble choice, and model limitations."""
    try:
        settings = get_settings()
        artifact_path = _resolve_backend_path(settings.model_artifact_path)
        metrics_path = artifact_path.with_suffix(".metrics.json")
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        classification = metrics["classification"]
        condemnation = metrics["condemnation"]
        return _json(
            {
                "status": "ok",
                "tool": "inspect_risk_model_card",
                "feature_policy": metrics["feature_policy"],
                "model_version": metrics["model_version"],
                "trained_at": metrics["trained_at"],
                "dataset": {
                    "rows": metrics["dataset"]["rows"],
                    "eligible_classification_rows": classification["eligible_rows"],
                    "excluded_agreements": classification["excluded_agreements"],
                    "held_out_test_rows": classification["test_rows"],
                },
                "selection": {
                    "champion": classification["selected_model"],
                    "ensemble_weights": classification["ensemble_weights"],
                },
                "held_out_classification": classification["test_champion"],
                "model_disagreement": classification["model_disagreement"],
                "condemnation": {
                    "test_rows": condemnation["test_rows"],
                    "mae": condemnation["model_mae"],
                    "rmse": condemnation["model_rmse"],
                    "r2": condemnation["model_r2"],
                    "q10_q90_coverage": condemnation["q10_q90_coverage"],
                },
                "top_permutation_features": classification["permutation_importance"][:6],
                "limitations": [
                    "Synthetic hackathon data; no external or temporal validation is available.",
                    (
                        "Agreement rows were excluded because they do not reveal the "
                        "counterfactual judgment."
                    ),
                    "Presence of a document does not prove its authenticity or factual content.",
                    (
                        "The severity model uses only the pre-judgment claim amount as a "
                        "monetary input and has held-out R² "
                        f"{condemnation['model_r2']:.3f}."
                    ),
                    (
                        "Performance may differ by court, time period, institution, and "
                        "data-generation process."
                    ),
                    (
                        "The model supports review; it must not determine the legal "
                        "disposition by itself."
                    ),
                ],
            }
        )
    except Exception as exc:
        return _json(
            {
                "status": "error",
                "tool": "inspect_risk_model_card",
                "error": str(exc),
            }
        )


ML_TOOLS = [estimate_case_risk, inspect_risk_model_card]
