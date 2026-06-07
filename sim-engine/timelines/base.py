from abc import ABC, abstractmethod
from typing import Any


class TimelineGenerator(ABC):
    """Generates deterministic score projections over time for a decision type."""

    @abstractmethod
    def generate(
        self,
        initial_scores: dict[str, dict[str, float]],
        anchors: dict[str, Any],
        years: list[str],
    ) -> dict[str, dict[str, dict[str, float]]]:
        """Returns {archetype: {year: {metric: score}}}."""
        ...

    @abstractmethod
    def node_names(self) -> list[str]:
        """The scoring nodes for this timeline."""
        ...


def _clamp(v: float) -> int:
    return max(5, min(100, int(v)))


def _causal_transition(prev: dict, year_gap: int) -> dict:
    """Simple drift + mean-reversion transition."""
    next_scores = {}
    for node, val in prev.items():
        drift = val + (50 - val) * 0.08 * year_gap + (year_gap * 2 - 4)
        next_scores[node] = _clamp(drift)
    return next_scores
