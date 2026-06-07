from decision_type import DecisionType
from timelines.base import TimelineGenerator
from timelines.educational import EducationalTimelineGenerator
from timelines.career import CareerTimelineGenerator
from timelines.financial import FinancialTimelineGenerator
from timelines.relocation import RelocationTimelineGenerator
from timelines.business import BusinessTimelineGenerator
from timelines.health import HealthTimelineGenerator
from timelines.relationship import RelationshipTimelineGenerator
from timelines.lifestyle import LifestyleTimelineGenerator


class TimelineGeneratorRegistry:
    _generators: dict[DecisionType, TimelineGenerator] = {
        DecisionType.EDUCATIONAL: EducationalTimelineGenerator(),
        DecisionType.CAREER: CareerTimelineGenerator(),
        DecisionType.FINANCIAL: FinancialTimelineGenerator(),
        DecisionType.BUSINESS: BusinessTimelineGenerator(),
        DecisionType.RELOCATION: RelocationTimelineGenerator(),
        DecisionType.HEALTH: HealthTimelineGenerator(),
        DecisionType.RELATIONSHIP: RelationshipTimelineGenerator(),
        DecisionType.LIFESTYLE: LifestyleTimelineGenerator(),
        DecisionType.GENERAL: CareerTimelineGenerator(),
    }

    def get_generator(self, decision_type: DecisionType) -> TimelineGenerator:
        return self._generators.get(decision_type, CareerTimelineGenerator())

    def register(self, decision_type: DecisionType, generator: TimelineGenerator) -> None:
        self._generators[decision_type] = generator


_registry: TimelineGeneratorRegistry | None = None


def get_timeline_generator(decision_type: DecisionType) -> TimelineGenerator:
    global _registry
    if _registry is None:
        _registry = TimelineGeneratorRegistry()
    return _registry.get_generator(decision_type)
