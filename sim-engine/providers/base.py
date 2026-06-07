from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ProviderContext:
    decision: str
    options: list[str]
    location: str
    raw_context: dict


@dataclass
class ProviderResult:
    context_data: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    confidence: int = 85
    collected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class DecisionProvider(ABC):
    """Base class for decision-type-specific data providers."""

    @abstractmethod
    def collect(self, ctx: ProviderContext) -> ProviderResult:
        ...

    @abstractmethod
    def metric_labels(self) -> list[str]:
        ...

    @abstractmethod
    def timeline_years(self) -> list[str]:
        ...
