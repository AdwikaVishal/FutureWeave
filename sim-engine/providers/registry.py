from decision_type import DecisionType
from providers.base import DecisionProvider
from providers.educational import EducationalProvider
from providers.career import CareerProvider
from providers.financial import FinancialProvider
from providers.business import BusinessProvider
from providers.relocation import RelocationProvider
from providers.health import HealthProvider
from providers.general import GeneralProvider
from providers.relationship import RelationshipProvider
from providers.lifestyle import LifestyleProvider


class ProviderRegistry:
    """Registry mapping DecisionType → DecisionProvider."""

    _providers: dict[DecisionType, DecisionProvider] = {
        DecisionType.EDUCATIONAL: EducationalProvider(),
        DecisionType.CAREER: CareerProvider(),
        DecisionType.FINANCIAL: FinancialProvider(),
        DecisionType.BUSINESS: BusinessProvider(),
        DecisionType.RELOCATION: RelocationProvider(),
        DecisionType.HEALTH: HealthProvider(),
        DecisionType.RELATIONSHIP: RelationshipProvider(),
        DecisionType.LIFESTYLE: LifestyleProvider(),
        DecisionType.GENERAL: GeneralProvider(),
    }

    def get_provider(self, decision_type: DecisionType) -> DecisionProvider:
        provider = self._providers.get(decision_type)
        if provider is None:
            return GeneralProvider()
        return provider

    def register(self, decision_type: DecisionType, provider: DecisionProvider) -> None:
        self._providers[decision_type] = provider


_registry_instance: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ProviderRegistry()
    return _registry_instance


def get_provider(decision_type: DecisionType) -> DecisionProvider:
    return get_provider_registry().get_provider(decision_type)
