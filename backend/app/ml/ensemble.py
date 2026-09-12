from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class ProbabilityEnsemble:
    """Weighted probability blend with inspectable component predictions."""

    estimators: tuple[Any, ...]
    estimator_names: tuple[str, ...]
    weights: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.estimators:
            raise ValueError("An ensemble requires at least one estimator")
        if len(self.estimators) != len(self.estimator_names) or len(self.estimators) != len(
            self.weights
        ):
            raise ValueError("Estimators, names, and weights must have equal lengths")
        if any(weight < 0 for weight in self.weights) or sum(self.weights) <= 0:
            raise ValueError("Ensemble weights must be non-negative with a positive sum")

    @property
    def classes_(self) -> NDArray[np.int64]:
        return np.asarray([0, 1], dtype=np.int64)

    def component_probabilities(self, features: Any) -> dict[str, NDArray[np.float64]]:
        return {
            name: np.asarray(estimator.predict_proba(features)[:, 1], dtype=np.float64)
            for name, estimator in zip(self.estimator_names, self.estimators, strict=True)
        }

    def predict_proba(self, features: Any) -> NDArray[np.float64]:
        components = self.component_probabilities(features)
        positive = np.average(
            np.vstack([components[name] for name in self.estimator_names]),
            axis=0,
            weights=np.asarray(self.weights, dtype=np.float64),
        )
        return np.column_stack((1.0 - positive, positive))

    def predict(self, features: Any) -> NDArray[np.int64]:
        return (self.predict_proba(features)[:, 1] >= 0.5).astype(np.int64)
