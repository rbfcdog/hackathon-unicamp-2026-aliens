from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    mean_absolute_error,
    mean_pinball_loss,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

from app.ml.ensemble import ProbabilityEnsemble

RANDOM_STATE = 42
ENSEMBLE_NAME = "logistic_xgboost_ensemble"
ENSEMBLE_WEIGHTS = {
    "logistic_regression": 0.70,
    "xgboost": 0.30,
}
OUTCOMES_SHEET = "Resultados dos processos"
SUBSIDIES_SHEET = "Subsídios disponibilizados"
PROCESS_COLUMN = "Número do processo"
SUBSIDY_PROCESS_COLUMN = "Número do processos"
MACRO_TARGET = "Resultado macro"
MICRO_TARGET = "Resultado micro"
VALUE_TARGET = "Valor da condenação/indenização"

CATEGORICAL_FEATURES = ["UF", "Sub-assunto"]
BINARY_FEATURES = [
    "Contrato",
    "Extrato",
    "Comprovante de crédito",
    "Dossiê",
    "Demonstrativo de evolução da dívida",
    "Laudo referenciado",
]
CLASSIFICATION_FEATURES = CATEGORICAL_FEATURES + BINARY_FEATURES
SEVERITY_FEATURES = CLASSIFICATION_FEATURES + ["Valor da causa"]
EXCLUDED_POST_OUTCOME_COLUMNS = [
    VALUE_TARGET,
    MACRO_TARGET,
    MICRO_TARGET,
    PROCESS_COLUMN,
    SUBSIDY_PROCESS_COLUMN,
]
FEATURE_POLICY = {
    "classification_input_features": CLASSIFICATION_FEATURES,
    "severity_input_features": SEVERITY_FEATURES,
    "severity_target": VALUE_TARGET,
    "excluded_post_outcome_columns": EXCLUDED_POST_OUTCOME_COLUMNS,
    "rationale": (
        "The pre-judgment claim amount is used only by the severity model. "
        "Paid, awarded, and outcome columns are never model inputs."
    ),
}

EXPECTED_OUTCOME_COLUMNS = {
    PROCESS_COLUMN,
    "UF",
    "Assunto",
    "Sub-assunto",
    MACRO_TARGET,
    MICRO_TARGET,
    "Valor da causa",
    VALUE_TARGET,
}
EXPECTED_SUBSIDY_COLUMNS = {SUBSIDY_PROCESS_COLUMN, *BINARY_FEATURES}
JUDICIAL_LOSS_RESULTS = {"Parcial procedência", "Procedência"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _report_path(path: Path) -> str:
    resolved = path.resolve()
    repository_root = Path(__file__).resolve().parents[2]
    try:
        return resolved.relative_to(repository_root).as_posix()
    except ValueError:
        return resolved.name


def _require_columns(actual: pd.Index, expected: set[str], sheet: str) -> None:
    missing = expected.difference(actual)
    unexpected = set(actual).difference(expected)
    if missing or unexpected:
        raise ValueError(
            f"Unexpected schema in {sheet}: missing={sorted(missing)}, "
            f"unexpected={sorted(unexpected)}"
        )


def load_training_data(workbook: Path) -> pd.DataFrame:
    outcomes = pd.read_excel(
        workbook,
        sheet_name=OUTCOMES_SHEET,
        dtype={PROCESS_COLUMN: "string"},
    )
    subsidies = pd.read_excel(
        workbook,
        sheet_name=SUBSIDIES_SHEET,
        header=1,
        dtype={SUBSIDY_PROCESS_COLUMN: "string"},
    )

    _require_columns(outcomes.columns, EXPECTED_OUTCOME_COLUMNS, OUTCOMES_SHEET)
    _require_columns(subsidies.columns, EXPECTED_SUBSIDY_COLUMNS, SUBSIDIES_SHEET)

    if outcomes.isna().any().any() or subsidies.isna().any().any():
        raise ValueError("Training workbook contains missing values")
    if outcomes[PROCESS_COLUMN].duplicated().any():
        raise ValueError("Outcome process numbers must be unique")
    if subsidies[SUBSIDY_PROCESS_COLUMN].duplicated().any():
        raise ValueError("Subsidy process numbers must be unique")

    for column in BINARY_FEATURES:
        invalid = set(subsidies[column].unique()).difference({0, 1})
        if invalid:
            raise ValueError(f"{column} contains non-binary values: {sorted(invalid)}")

    merged = outcomes.merge(
        subsidies,
        left_on=PROCESS_COLUMN,
        right_on=SUBSIDY_PROCESS_COLUMN,
        how="inner",
        validate="one_to_one",
    )
    if len(merged) != len(outcomes) or len(merged) != len(subsidies):
        raise ValueError("Outcome and subsidy process IDs do not match exactly")
    return merged


def _preprocessor(*, dense: bool, include_claim_amount: bool) -> ColumnTransformer:
    transformers: list[tuple[str, Any, list[str]]] = [
        (
            "categorical",
            OneHotEncoder(handle_unknown="ignore", sparse_output=not dense),
            CATEGORICAL_FEATURES,
        )
    ]
    if include_claim_amount:
        transformers.append(("claim_amount", StandardScaler(), ["Valor da causa"]))
    transformers.append(("binary", "passthrough", BINARY_FEATURES))
    return ColumnTransformer(transformers=transformers)


def _base_classifier(name: str) -> Pipeline:
    if name == "logistic_regression":
        estimator = LogisticRegression(max_iter=2_000, random_state=RANDOM_STATE)
        return Pipeline(
            [
                (
                    "preprocessor",
                    _preprocessor(dense=False, include_claim_amount=False),
                ),
                ("classifier", estimator),
            ]
        )
    if name == "xgboost":
        estimator = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            tree_method="hist",
            n_estimators=300,
            learning_rate=0.04,
            max_depth=3,
            min_child_weight=10,
            subsample=0.90,
            colsample_bytree=0.90,
            reg_alpha=0.10,
            reg_lambda=2.0,
            random_state=RANDOM_STATE,
            n_jobs=1,
        )
        return Pipeline(
            [
                (
                    "preprocessor",
                    _preprocessor(dense=False, include_claim_amount=False),
                ),
                ("classifier", estimator),
            ]
        )
    raise ValueError(f"Unknown classifier: {name}")


def _calibrated_classifier(name: str) -> CalibratedClassifierCV:
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    return CalibratedClassifierCV(
        estimator=_base_classifier(name),
        method="sigmoid",
        cv=folds,
        n_jobs=-1,
        ensemble=False,
    )


def _expected_calibration_error(y_true: pd.Series, probabilities: np.ndarray) -> float:
    error = 0.0
    bins = np.linspace(0.0, 1.0, 11)
    y_values = y_true.to_numpy()
    for index, (lower, upper) in enumerate(zip(bins[:-1], bins[1:], strict=True)):
        if index == len(bins) - 2:
            mask = (probabilities >= lower) & (probabilities <= upper)
        else:
            mask = (probabilities >= lower) & (probabilities < upper)
        if not mask.any():
            continue
        observed = float(y_values[mask].mean())
        predicted = float(probabilities[mask].mean())
        error += float(mask.mean()) * abs(observed - predicted)
    return error


def _calibration_bins(y_true: pd.Series, probabilities: np.ndarray) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    y_values = y_true.to_numpy()
    for lower in np.linspace(0.0, 0.9, 10):
        upper = lower + 0.1
        mask = (probabilities >= lower) & (
            probabilities <= upper if upper >= 1.0 else probabilities < upper
        )
        if not mask.any():
            continue
        rows.append(
            {
                "lower": float(lower),
                "upper": float(min(upper, 1.0)),
                "count": int(mask.sum()),
                "mean_probability": float(probabilities[mask].mean()),
                "observed_loss_rate": float(y_values[mask].mean()),
            }
        )
    return rows


def classification_metrics(y_true: pd.Series, probabilities: np.ndarray) -> dict[str, Any]:
    predictions = (probabilities >= 0.5).astype(int)
    true_negative, false_positive, false_negative, true_positive = confusion_matrix(
        y_true, predictions, labels=[0, 1]
    ).ravel()
    return {
        "roc_auc": float(roc_auc_score(y_true, probabilities)),
        "average_precision": float(average_precision_score(y_true, probabilities)),
        "brier_score": float(brier_score_loss(y_true, probabilities)),
        "log_loss": float(log_loss(y_true, probabilities)),
        "expected_calibration_error": _expected_calibration_error(y_true, probabilities),
        "accuracy_at_0_5": float(accuracy_score(y_true, predictions)),
        "precision_at_0_5": float(precision_score(y_true, predictions)),
        "recall_at_0_5": float(recall_score(y_true, predictions)),
        "f1_at_0_5": float(f1_score(y_true, predictions)),
        "confusion_matrix_at_0_5": {
            "true_negative": int(true_negative),
            "false_positive": int(false_positive),
            "false_negative": int(false_negative),
            "true_positive": int(true_positive),
        },
        "calibration_bins": _calibration_bins(y_true, probabilities),
    }


def _segmented_metrics(
    features: pd.DataFrame,
    target: pd.Series,
    probabilities: np.ndarray,
) -> dict[str, list[dict[str, Any]]]:
    segments: dict[str, list[dict[str, Any]]] = {}
    for feature in ("UF", "Sub-assunto"):
        rows: list[dict[str, Any]] = []
        for value in sorted(features[feature].unique()):
            mask = (features[feature] == value).to_numpy()
            segment_target = target.iloc[np.flatnonzero(mask)]
            segment_probabilities = probabilities[mask]
            rows.append(
                {
                    "value": value,
                    "rows": int(mask.sum()),
                    "loss_rate": float(segment_target.mean()),
                    "roc_auc": float(roc_auc_score(segment_target, segment_probabilities)),
                    "brier_score": float(brier_score_loss(segment_target, segment_probabilities)),
                    "accuracy_at_0_5": float(
                        accuracy_score(segment_target, (segment_probabilities >= 0.5).astype(int))
                    ),
                }
            )
        segments[feature] = rows
    return segments


def _permutation_importance(
    classifier: Any,
    features: pd.DataFrame,
    target: pd.Series,
    probabilities: np.ndarray,
) -> list[dict[str, Any]]:
    baseline_brier = brier_score_loss(target, probabilities)
    baseline_auc = roc_auc_score(target, probabilities)
    random = np.random.default_rng(RANDOM_STATE)
    rows: list[dict[str, Any]] = []
    for feature in CLASSIFICATION_FEATURES:
        permuted = features.copy()
        permuted[feature] = random.permutation(permuted[feature].to_numpy())
        permuted_probabilities = classifier.predict_proba(permuted)[:, 1]
        rows.append(
            {
                "feature": feature,
                "brier_increase": float(
                    brier_score_loss(target, permuted_probabilities) - baseline_brier
                ),
                "roc_auc_drop": float(baseline_auc - roc_auc_score(target, permuted_probabilities)),
            }
        )
    return sorted(rows, key=lambda row: row["brier_increase"], reverse=True)


def train_loss_classifier(
    data: pd.DataFrame,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    judicial = data.loc[data[MICRO_TARGET] != "Acordo"].copy()
    features = judicial[CLASSIFICATION_FEATURES]
    target = (judicial[MACRO_TARGET] == "Não Êxito").astype(int)

    development_x, test_x, development_y, test_y = train_test_split(
        features,
        target,
        test_size=0.20,
        random_state=RANDOM_STATE,
        stratify=target,
    )
    train_x, validation_x, train_y, validation_y = train_test_split(
        development_x,
        development_y,
        test_size=0.25,
        random_state=RANDOM_STATE,
        stratify=development_y,
    )

    validation_models = {
        name: _calibrated_classifier(name) for name in ("logistic_regression", "xgboost")
    }
    validation_probabilities: dict[str, np.ndarray] = {}
    validation_metrics: dict[str, dict[str, Any]] = {}
    for name, candidate in validation_models.items():
        candidate.fit(train_x, train_y)
        probabilities = candidate.predict_proba(validation_x)[:, 1]
        validation_probabilities[name] = probabilities
        validation_metrics[name] = classification_metrics(validation_y, probabilities)

    logistic_weight = ENSEMBLE_WEIGHTS["logistic_regression"]
    xgboost_weight = ENSEMBLE_WEIGHTS["xgboost"]
    validation_ensemble = ProbabilityEnsemble(
        estimators=(
            validation_models["logistic_regression"],
            validation_models["xgboost"],
        ),
        estimator_names=("logistic_regression", "xgboost"),
        weights=(logistic_weight, xgboost_weight),
    )
    validation_ensemble_probabilities = validation_ensemble.predict_proba(validation_x)[:, 1]
    validation_metrics[ENSEMBLE_NAME] = classification_metrics(
        validation_y, validation_ensemble_probabilities
    )
    selected_name = ENSEMBLE_NAME

    final_components = {
        name: _calibrated_classifier(name) for name in ("logistic_regression", "xgboost")
    }
    for model in final_components.values():
        model.fit(development_x, development_y)
    final_ensemble = ProbabilityEnsemble(
        estimators=(
            final_components["logistic_regression"],
            final_components["xgboost"],
        ),
        estimator_names=("logistic_regression", "xgboost"),
        weights=(logistic_weight, xgboost_weight),
    )
    final_candidates: dict[str, Any] = {
        **final_components,
        ENSEMBLE_NAME: final_ensemble,
    }
    classifier = final_candidates[selected_name]

    test_probabilities = {
        name: model.predict_proba(test_x)[:, 1] for name, model in final_candidates.items()
    }
    champion_probabilities = test_probabilities[selected_name]
    validation_disagreement = np.abs(
        validation_probabilities["logistic_regression"] - validation_probabilities["xgboost"]
    )
    disagreement_threshold = float(np.quantile(validation_disagreement, 0.95))
    test_disagreement = np.abs(
        test_probabilities["logistic_regression"] - test_probabilities["xgboost"]
    )

    model_metadata = {
        "components": final_components,
        "ensemble_weights": dict(ENSEMBLE_WEIGHTS),
        "disagreement_threshold": disagreement_threshold,
    }
    metrics = {
        "eligible_rows": int(len(judicial)),
        "excluded_agreements": int((data[MICRO_TARGET] == "Acordo").sum()),
        "development_rows": int(len(development_x)),
        "test_rows": int(len(test_x)),
        "test_loss_rate": float(test_y.mean()),
        "selection_rule": "fixed 70% logistic regression and 30% XGBoost blend",
        "validation_candidates": validation_metrics,
        "ensemble_weights": dict(ENSEMBLE_WEIGHTS),
        "selected_model": selected_name,
        "test_candidates": {
            name: classification_metrics(test_y, probabilities)
            for name, probabilities in test_probabilities.items()
        },
        "test_champion": classification_metrics(test_y, champion_probabilities),
        "model_disagreement": {
            "validation_p95_threshold": disagreement_threshold,
            "test_mean": float(test_disagreement.mean()),
            "test_p95": float(np.quantile(test_disagreement, 0.95)),
            "test_above_threshold_rate": float((test_disagreement > disagreement_threshold).mean()),
        },
        "segmented_test_metrics": _segmented_metrics(test_x, test_y, champion_probabilities),
        "permutation_importance": _permutation_importance(
            classifier, test_x, test_y, champion_probabilities
        ),
    }
    return classifier, model_metadata, metrics


def _regressor(*, loss: str, quantile: float | None = None) -> Pipeline:
    parameters: dict[str, Any] = {
        "loss": loss,
        "learning_rate": 0.06,
        "max_iter": 250,
        "max_leaf_nodes": 15,
        "l2_regularization": 1.0,
        "random_state": RANDOM_STATE,
    }
    if quantile is not None:
        parameters["quantile"] = quantile
    estimator = HistGradientBoostingRegressor(**parameters)
    return Pipeline(
        [
            ("preprocessor", _preprocessor(dense=True, include_claim_amount=True)),
            ("regressor", estimator),
        ]
    )


def train_condemnation_models(
    data: pd.DataFrame,
) -> tuple[dict[str, Pipeline], dict[str, Any]]:
    losses = data.loc[data[MICRO_TARGET].isin(JUDICIAL_LOSS_RESULTS)].copy()
    train_rows, test_rows = train_test_split(
        losses.index,
        test_size=0.20,
        random_state=RANDOM_STATE,
        stratify=losses[MICRO_TARGET],
    )
    train = losses.loc[train_rows]
    test = losses.loc[test_rows]

    models = {
        "mean": _regressor(loss="squared_error"),
        "q10": _regressor(loss="quantile", quantile=0.10),
        "q50": _regressor(loss="quantile", quantile=0.50),
        "q90": _regressor(loss="quantile", quantile=0.90),
    }
    for model in models.values():
        model.fit(train[SEVERITY_FEATURES], train[VALUE_TARGET])

    actual = test[VALUE_TARGET].to_numpy()
    predictions = {
        name: np.maximum(model.predict(test[SEVERITY_FEATURES]), 0.0)
        for name, model in models.items()
    }
    lower = predictions["q10"]
    upper = predictions["q90"]
    crossing = lower > upper
    interval_lower = np.minimum(lower, upper)
    interval_upper = np.maximum(lower, upper)
    baseline = np.full_like(actual, train[VALUE_TARGET].mean(), dtype=float)

    by_result: dict[str, Any] = {}
    for result in sorted(JUDICIAL_LOSS_RESULTS):
        mask = test[MICRO_TARGET].to_numpy() == result
        by_result[result] = {
            "rows": int(mask.sum()),
            "mae": float(mean_absolute_error(actual[mask], predictions["mean"][mask])),
            "mean_actual": float(actual[mask].mean()),
            "mean_prediction": float(predictions["mean"][mask].mean()),
        }

    metrics = {
        "eligible_rows": int(len(losses)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "test_target_mean": float(actual.mean()),
        "test_target_median": float(np.median(actual)),
        "mean_baseline_mae": float(mean_absolute_error(actual, baseline)),
        "model_mae": float(mean_absolute_error(actual, predictions["mean"])),
        "model_rmse": float(np.sqrt(mean_squared_error(actual, predictions["mean"]))),
        "model_r2": float(r2_score(actual, predictions["mean"])),
        "q10_pinball_loss": float(mean_pinball_loss(actual, predictions["q10"], alpha=0.10)),
        "q50_pinball_loss": float(mean_pinball_loss(actual, predictions["q50"], alpha=0.50)),
        "q90_pinball_loss": float(mean_pinball_loss(actual, predictions["q90"], alpha=0.90)),
        "q10_q90_coverage": float(((actual >= interval_lower) & (actual <= interval_upper)).mean()),
        "q10_q90_mean_width": float((interval_upper - interval_lower).mean()),
        "quantile_crossing_rows": int(crossing.sum()),
        "by_result_micro": by_result,
    }
    return models, metrics


def _example_cases() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "case": "case_01",
                "UF": "MA",
                "Sub-assunto": "Genérico",
                "Valor da causa": 20_000.0,
                "Contrato": 1,
                "Extrato": 1,
                "Comprovante de crédito": 1,
                "Dossiê": 1,
                "Demonstrativo de evolução da dívida": 1,
                "Laudo referenciado": 1,
            },
            {
                "case": "case_02",
                "UF": "AM",
                "Sub-assunto": "Golpe",
                "Valor da causa": 25_000.0,
                "Contrato": 0,
                "Extrato": 0,
                "Comprovante de crédito": 1,
                "Dossiê": 0,
                "Demonstrativo de evolução da dívida": 1,
                "Laudo referenciado": 1,
            },
        ]
    )


def example_predictions(
    classifier: Any,
    classifier_components: dict[str, Any],
    condemnation_models: dict[str, Pipeline],
) -> list[dict[str, Any]]:
    examples = _example_cases()
    probabilities = classifier.predict_proba(examples[CLASSIFICATION_FEATURES])[:, 1]
    component_probabilities = {
        name: model.predict_proba(examples[CLASSIFICATION_FEATURES])[:, 1]
        for name, model in classifier_components.items()
    }
    amount_predictions = {
        name: np.maximum(model.predict(examples[SEVERITY_FEATURES]), 0.0)
        for name, model in condemnation_models.items()
    }
    rows: list[dict[str, Any]] = []
    for index, case in examples.iterrows():
        conditional_mean = float(amount_predictions["mean"][index])
        logistic_probability = float(component_probabilities["logistic_regression"][index])
        xgboost_probability = float(component_probabilities["xgboost"][index])
        rows.append(
            {
                "case": case["case"],
                "loss_probability": float(probabilities[index]),
                "logistic_probability": logistic_probability,
                "xgboost_probability": xgboost_probability,
                "model_disagreement": abs(logistic_probability - xgboost_probability),
                "conditional_expected_condemnation": conditional_mean,
                "expected_judicial_exposure": float(probabilities[index] * conditional_mean),
                "condemnation_q10": float(amount_predictions["q10"][index]),
                "condemnation_q50": float(amount_predictions["q50"][index]),
                "condemnation_q90": float(amount_predictions["q90"][index]),
            }
        )
    return rows


def verify_artifact(
    artifact_path: Path, expected_predictions: list[dict[str, Any]]
) -> dict[str, Any]:
    loaded = joblib.load(artifact_path)
    required_keys = {
        "format_version",
        "model_version",
        "dataset_sha256",
        "classification_features",
        "severity_features",
        "feature_policy",
        "classifier",
        "classifier_components",
        "ensemble_weights",
        "model_disagreement_threshold",
        "condemnation_models",
    }
    missing_keys = required_keys.difference(loaded)
    if missing_keys:
        raise ValueError(f"Reloaded artifact is missing keys: {sorted(missing_keys)}")
    classifier = loaded["classifier"]
    if not isinstance(classifier, ProbabilityEnsemble):
        raise ValueError("Reloaded classifier is not the fixed probability ensemble")
    actual_weights = dict(zip(classifier.estimator_names, classifier.weights, strict=True))
    if loaded["ensemble_weights"] != ENSEMBLE_WEIGHTS or actual_weights != ENSEMBLE_WEIGHTS:
        raise ValueError("Reloaded ensemble weights are not 70% logistic and 30% XGBoost")

    reloaded_predictions = example_predictions(
        loaded["classifier"],
        loaded["classifier_components"],
        loaded["condemnation_models"],
    )
    if len(reloaded_predictions) != len(expected_predictions):
        raise ValueError("Reloaded artifact returned a different number of predictions")

    for expected, actual in zip(expected_predictions, reloaded_predictions, strict=True):
        if expected["case"] != actual["case"]:
            raise ValueError("Reloaded artifact changed example case order")
        for field in expected.keys() - {"case"}:
            if not np.isclose(expected[field], actual[field], rtol=1e-12, atol=1e-12):
                raise ValueError(f"Reloaded artifact changed {expected['case']} field {field}")

    return {
        "reloaded": True,
        "example_predictions_match": True,
        "size_bytes": artifact_path.stat().st_size,
    }


def train(workbook: Path, output_dir: Path, model_version: str) -> dict[str, Any]:
    workbook = workbook.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    data = load_training_data(workbook)
    forbidden_risk_features = {"Valor da causa", *EXCLUDED_POST_OUTCOME_COLUMNS}.intersection(
        CLASSIFICATION_FEATURES
    )
    forbidden_severity_features = set(EXCLUDED_POST_OUTCOME_COLUMNS).intersection(SEVERITY_FEATURES)
    if forbidden_risk_features or forbidden_severity_features:
        raise ValueError(
            "Forbidden model features configured: "
            f"risk={sorted(forbidden_risk_features)}, "
            f"severity={sorted(forbidden_severity_features)}"
        )

    classifier, classifier_metadata, classification = train_loss_classifier(data)
    condemnation_models, condemnation = train_condemnation_models(data)
    predictions = example_predictions(
        classifier, classifier_metadata["components"], condemnation_models
    )

    trained_at = datetime.now(UTC).isoformat()
    dataset_hash = _sha256(workbook)
    artifact_path = output_dir / f"{model_version}.joblib"
    metrics_path = output_dir / f"{model_version}.metrics.json"

    bundle = {
        "format_version": 4,
        "model_version": model_version,
        "trained_at": trained_at,
        "dataset_sha256": dataset_hash,
        "classification_features": CLASSIFICATION_FEATURES,
        "severity_features": SEVERITY_FEATURES,
        "feature_policy": FEATURE_POLICY,
        "classifier": classifier,
        "classifier_components": classifier_metadata["components"],
        "ensemble_weights": classifier_metadata["ensemble_weights"],
        "model_disagreement_threshold": classifier_metadata["disagreement_threshold"],
        "condemnation_models": condemnation_models,
    }
    joblib.dump(bundle, artifact_path, compress=3)
    artifact_verification = verify_artifact(artifact_path, predictions)

    report = {
        "model_version": model_version,
        "trained_at": trained_at,
        "dataset": {
            "path": _report_path(workbook),
            "sha256": dataset_hash,
            "rows": int(len(data)),
        },
        "feature_policy": FEATURE_POLICY,
        "classification": classification,
        "condemnation": condemnation,
        "example_predictions": predictions,
        "artifact_path": _report_path(artifact_path),
        "artifact_verification": artifact_verification,
    }
    metrics_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    repository_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Train leakage-safe calibrated judicial-risk and condemnation models."
    )
    parser.add_argument(
        "--workbook",
        type=Path,
        default=repository_root / "data" / "datasets" / "Hackaton_Enter_Base_Candidatos.xlsx",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repository_root / "backend" / "artifacts",
    )
    parser.add_argument("--model-version", default="judicial-risk-v5")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = train(args.workbook, args.output_dir, args.model_version)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
