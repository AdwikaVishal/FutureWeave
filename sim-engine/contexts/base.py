from abc import ABC, abstractmethod
from typing import Any


class ContextBuilder(ABC):
    """Builds the context/simulation state for a decision type."""

    @abstractmethod
    def build_anchors(self, provider_data: dict[str, Any]) -> dict[str, Any]:
        ...

    @abstractmethod
    def build_initial_scores(self, provider_data: dict[str, Any]) -> dict[str, dict[str, float]]:
        """Return archetype -> {metric: score} for Year 1."""
        ...

    @abstractmethod
    def ignore_income(self) -> bool:
        """Whether this decision type should skip income/salary scoring."""
        ...

    @abstractmethod
    def primary_metrics(self) -> list[str]:
        """The metrics that matter most for this decision type."""
        ...


SCORE_CLAMP = lambda v: max(5, min(100, int(v)))
