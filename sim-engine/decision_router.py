import logging

from decision_type import DecisionType
from providers.base import DecisionProvider
from providers.registry import get_provider

logger = logging.getLogger(__name__)


class DecisionRouter:
    """Routes a decision type to its provider, context builder, and timeline."""

    def get_provider(self, decision_type: DecisionType) -> DecisionProvider:
        return get_provider(decision_type)

    def verify(self, decision_type: DecisionType) -> dict:
        provider = self.get_provider(decision_type)
        timeline_labels = provider.timeline_templates()
        return {
            "decision_type": decision_type.value,
            "provider": provider.__class__.__name__,
            "timeline": timeline_labels,
            "metrics": provider.metric_labels(),
        }


def route_decision(decision_type: DecisionType) -> dict:
    router = DecisionRouter()
    info = router.verify(decision_type)

    logger.info(
        "\n=== DECISION ROUTING ===\n"
        "TYPE=%s\n"
        "ROUTER=%s\n"
        "PROVIDER=%s\n"
        "TIMELINE=%s\n"
        "METRICS=%s\n"
        "=========================",
        info["decision_type"],
        "DecisionRouter",
        info["provider"],
        list(info["timeline"].values()),
        info["metrics"],
    )

    provider_type = info["provider"]
    expected = {
        DecisionType.EDUCATIONAL: "EducationalProvider",
        DecisionType.CAREER: "CareerProvider",
        DecisionType.FINANCIAL: "FinancialProvider",
        DecisionType.BUSINESS: "BusinessProvider",
        DecisionType.RELOCATION: "RelocationProvider",
        DecisionType.HEALTH: "HealthProvider",
    }

    expected_provider = expected.get(decision_type, "GeneralProvider")
    if provider_type != expected_provider:
        raise RuntimeError(
            f"ROUTING MISMATCH: decision_type={decision_type.value} "
            f"got provider={provider_type} expected={expected_provider}. "
            "Aborting simulation."
        )

    return info
