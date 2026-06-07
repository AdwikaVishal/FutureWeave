from enum import Enum


class DecisionType(str, Enum):
    EDUCATIONAL = "educational"
    CAREER = "career"
    FINANCIAL = "financial"
    BUSINESS = "business"
    RELOCATION = "relocation"
    HEALTH = "health"
    RELATIONSHIP = "relationship"
    LIFESTYLE = "lifestyle"
    GENERAL = "general"


DECISION_TYPES_WITH_SALARY = {DecisionType.CAREER, DecisionType.GENERAL}
DECISION_TYPES_WITH_MACRO = {DecisionType.CAREER, DecisionType.FINANCIAL, DecisionType.BUSINESS, DecisionType.RELOCATION}
DECISION_TYPES_WITH_COST_OF_LIVING = {
    DecisionType.CAREER, DecisionType.FINANCIAL, DecisionType.HEALTH,
    DecisionType.RELOCATION, DecisionType.BUSINESS, DecisionType.LIFESTYLE,
}
DECISION_TYPES_WITH_JOB_MARKET = {DecisionType.CAREER, DecisionType.RELOCATION}
DECISION_TYPES_WITH_EDUCATION = {DecisionType.EDUCATIONAL}
DECISION_TYPES_WITH_HEALTH = {DecisionType.HEALTH}
DECISION_TYPES_WITH_BUSINESS = {DecisionType.BUSINESS}
DECISION_TYPES_WITH_IMMIGRATION = {DecisionType.RELOCATION}
