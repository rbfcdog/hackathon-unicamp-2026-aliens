from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import joblib
import pandas as pd

from app.ml.ensemble import ProbabilityEnsemble
from app.schemas.analysis import EvidenceInput

_CLASSIFICATION_FEATURE_COLUMNS = [
    "UF",
    "Sub-assunto",
    "Contrato",
    "Extrato",
    "Comprovante de crédito",
    "Dossiê",
    "Demonstrativo de evolução da dívida",
    "Laudo referenciado",
]
_SEVERITY_FEATURE_COLUMNS = [*_CLASSIFICATION_FEATURE_COLUMNS, "Valor da causa"]
_POST_OUTCOME_COLUMNS = {
    "Valor da condenação/indenização",
    "Resultado macro",
    "Resultado micro",
}
_EXPECTED_ENSEMBLE_WEIGHTS = {
    "logistic_regression": 0.7,
    "xgboost": 0.3,
}


@dataclass(frozen=True)
class RiskEstimate:
    loss_probability: float
    expected_condemnation: float
    condemnation_q10: float
    condemnation_q50: float
    condemnation_q90: float
    model_disagreement: float
    component_probabilities: dict[str, float]
    ensemble_weights: dict[str, float]
    requires_model_review: bool
    model_version: str


class TrainedRiskModel:
    """Versioned risk and severity models loaded from a trusted local artifact."""

    def __init__(self, artifact_path: str | Path = "artifacts/judicial-risk-v5.joblib") -> None:
        path = Path(artifact_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        if not path.is_file():
            raise FileNotFoundError(f"Model artifact not found: {path}")

        bundle: dict[str, Any] = joblib.load(path)
        required = {
            "format_version",
            "feature_policy",
            "model_version",
            "classification_features",
            "severity_features",
            "classifier",
            "classifier_components",
            "ensemble_weights",
            "model_disagreement_threshold",
            "condemnation_models",
        }
        missing = required.difference(bundle)
        if missing:
            raise ValueError(f"Model artifact is missing keys: {sorted(missing)}")
        if bundle["format_version"] != 4:
            raise ValueError("Model artifact format is not task-specific version 4")
        if _POST_OUTCOME_COLUMNS.intersection(bundle["classification_features"]):
            raise ValueError("Risk classifier contains a post-outcome feature")
        if _POST_OUTCOME_COLUMNS.intersection(bundle["severity_features"]):
            raise ValueError("Severity model contains a post-outcome feature")
        if "Valor da causa" in bundle["classification_features"]:
            raise ValueError("Risk classifier must not use the claim amount")
        if bundle["classification_features"] != _CLASSIFICATION_FEATURE_COLUMNS:
            raise ValueError("Risk classifier feature schema does not match runtime schema")
        if bundle["severity_features"] != _SEVERITY_FEATURE_COLUMNS:
            raise ValueError("Severity model feature schema does not match runtime schema")
        classifier = bundle["classifier"]
        if not isinstance(classifier, ProbabilityEnsemble):
            raise ValueError("Risk classifier must be the fixed logistic/XGBoost ensemble")
        actual_weights = dict(zip(classifier.estimator_names, classifier.weights, strict=True))
        if (
            bundle["ensemble_weights"] != _EXPECTED_ENSEMBLE_WEIGHTS
            or actual_weights != _EXPECTED_ENSEMBLE_WEIGHTS
        ):
            raise ValueError("Risk ensemble weights must be 70% logistic and 30% XGBoost")

        self._bundle = bundle

    @property
    def model_version(self) -> str:
        return str(self._bundle["model_version"])

    @staticmethod
    def _features(
        state: str,
        sub_subject: Literal["fraud", "generic"],
        claim_amount: float,
        evidence: EvidenceInput,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        common = {
            "UF": state.upper(),
            "Sub-assunto": "Golpe" if sub_subject == "fraud" else "Genérico",
            "Contrato": int(evidence.contract),
            "Extrato": int(evidence.bank_statement),
            "Comprovante de crédito": int(evidence.credit_proof),
            "Dossiê": int(evidence.dossier),
            "Demonstrativo de evolução da dívida": int(evidence.debt_evolution),
            "Laudo referenciado": int(evidence.referenced_report),
        }
        classification = pd.DataFrame([common], columns=_CLASSIFICATION_FEATURE_COLUMNS)
        severity = pd.DataFrame(
            [{**common, "Valor da causa": claim_amount}],
            columns=_SEVERITY_FEATURE_COLUMNS,
        )
        return classification, severity

    def predict(
        self,
        *,
        state: str,
        sub_subject: Literal["fraud", "generic"],
        claim_amount: float,
        evidence: EvidenceInput,
    ) -> RiskEstimate:
        classification_features, severity_features = self._features(
            state,
            sub_subject,
            claim_amount,
            evidence,
        )
        loss_probability = float(
            self._bundle["classifier"].predict_proba(classification_features)[0, 1]
        )
        components = {
            name: float(model.predict_proba(classification_features)[0, 1])
            for name, model in self._bundle["classifier_components"].items()
        }
        model_disagreement = max(components.values()) - min(components.values())

        condemnation_models = self._bundle["condemnation_models"]
        expected_condemnation = max(
            float(condemnation_models["mean"].predict(severity_features)[0]),
            0.0,
        )
        quantiles = [
            max(float(condemnation_models[name].predict(severity_features)[0]), 0.0)
            for name in ("q10", "q50", "q90")
        ]
        if quantiles != sorted(quantiles):
            raise ValueError("Condemnation model returned crossed quantiles")

        return RiskEstimate(
            loss_probability=round(loss_probability, 6),
            expected_condemnation=round(expected_condemnation, 2),
            condemnation_q10=round(quantiles[0], 2),
            condemnation_q50=round(quantiles[1], 2),
            condemnation_q90=round(quantiles[2], 2),
            model_disagreement=round(model_disagreement, 6),
            component_probabilities={
                name: round(probability, 6) for name, probability in components.items()
            },
            ensemble_weights=dict(self._bundle["ensemble_weights"]),
            requires_model_review=(
                model_disagreement > float(self._bundle["model_disagreement_threshold"])
            ),
            model_version=self.model_version,
        )
