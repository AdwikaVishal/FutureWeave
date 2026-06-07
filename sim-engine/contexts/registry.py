from decision_type import DecisionType
from contexts.base import ContextBuilder
from contexts.educational import EducationalContextBuilder
from contexts.career import CareerContextBuilder
from contexts.financial import FinancialContextBuilder
from contexts.relocation import RelocationContextBuilder
from contexts.business import BusinessContextBuilder
from contexts.health import HealthContextBuilder
from contexts.relationship import RelationshipContextBuilder
from contexts.lifestyle import LifestyleContextBuilder


class ContextBuilderRegistry:
    _builders: dict[DecisionType, ContextBuilder] = {
        DecisionType.EDUCATIONAL: EducationalContextBuilder(),
        DecisionType.CAREER: CareerContextBuilder(),
        DecisionType.FINANCIAL: FinancialContextBuilder(),
        DecisionType.BUSINESS: BusinessContextBuilder(),
        DecisionType.RELOCATION: RelocationContextBuilder(),
        DecisionType.HEALTH: HealthContextBuilder(),
        DecisionType.RELATIONSHIP: RelationshipContextBuilder(),
        DecisionType.LIFESTYLE: LifestyleContextBuilder(),
        DecisionType.GENERAL: CareerContextBuilder(),
    }

    def get_builder(self, decision_type: DecisionType) -> ContextBuilder:
        return self._builders.get(decision_type, CareerContextBuilder())

    def register(self, decision_type: DecisionType, builder: ContextBuilder) -> None:
        self._builders[decision_type] = builder


_registry: ContextBuilderRegistry | None = None


def get_context_builder(decision_type: DecisionType) -> ContextBuilder:
    global _registry
    if _registry is None:
        _registry = ContextBuilderRegistry()
    return _registry.get_builder(decision_type)
