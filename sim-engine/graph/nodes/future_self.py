"""
Future Self node — generates living personas for each timeline using a single batched LLM call.
"""
import logging
import time

from graph.state import SimulationState, SimulationPhase, FutureSelfState

logger = logging.getLogger(__name__)


def future_self_node(state: SimulationState) -> SimulationState:
    logger.info("[Node] Generating Future Self personas (batched)")
    state.phase = SimulationPhase.FUTURE_SELF
    start = time.time()

    from graph.agents.future_self import FutureSelfAgent

    agent = FutureSelfAgent()
    archetypes = {tl: state.timelines[tl].archetype for tl in state.timelines}

    personas = agent.create_all_personas(
        decision=state.decision,
        context=state.context,
        archetypes=archetypes,
    )

    for tl_key, persona in personas.items():
        if persona and persona.get("name"):
            state.future_selves[tl_key] = FutureSelfState(
                timeline_label=tl_key,
                persona=persona.get("name", ""),
                biography=persona.get("biography", ""),
                perspectives=persona.get("perspectives", {}),
            )
        else:
            state.future_selves[tl_key] = _fallback_future_self(tl_key, archetypes.get(tl_key, "The Settler"), state.decision)

    state.phase = SimulationPhase.SYNTHESIS
    logger.info("[Node] Future Self personas generated in %.0fms", (time.time() - start) * 1000)
    return state


def _fallback_future_self(tl_key: str, archetype: str, decision: str) -> FutureSelfState:
    templates = {
        "The Settler": {
            "name": "Arjun",
            "biography": f"I chose the steady path. Ten years after deciding to {decision[:50]}, I built a life of quiet competence. The career progressed predictably, relationships deepened slowly, and health stayed intact. I don't regret the stability — I regret not asking 'what if' more often.",
            "perspectives": {
                "on_risk": "Risk is relative. The risk of losing what you have sometimes outweighs the reward of gaining more.",
                "on_career": "Compounding consistency beats sporadic brilliance over a decade.",
                "on_relationships": "People stay when you show up consistently, not spectacularly.",
                "on_health": "Health is the foundation. Everything else is built on it.",
                "on_money": "Enough is a feeling, not a number. I learned this too late to act on it.",
                "on_the_path_not_taken": "I sometimes wonder about the bold choices. But wonder is not regret.",
            },
        },
        "The Climber": {
            "name": "Priya",
            "biography": f"I chose ambition. When I decided to {decision[:50]}, I committed fully. The climb was exhilarating and exhausting. I reached heights I dreamed of, but the view from the top includes a few empty seats — relationships I didn't nurture, health I didn't prioritize. Worth it? Mostly.",
            "perspectives": {
                "on_risk": "Calculated risks compound. The ones that scare you most often pay off best.",
                "on_career": "Your career is a rocket ship. Don't be afraid to change trajectory mid-flight.",
                "on_relationships": "The people who matter will wait. The ones who don't, won't. Both are useful signals.",
                "on_health": "You can't climb if the ladder breaks. Health is maintenance, not repair.",
                "on_money": "Money amplifies who you already are. It doesn't fix who you're not.",
                "on_the_path_not_taken": "I don't regret climbing. I regret not enjoying the view more along the way.",
            },
        },
        "The Gambler": {
            "name": "Ravi",
            "biography": f"I chose the bet. When I decided to {decision[:50]}, friends called it reckless. Maybe it was. But ten years later, the gambles that paid off defined me, and the ones that didn't taught me. I'd rather live with scars from the fight than with the ache of never having fought.",
            "perspectives": {
                "on_risk": "The biggest risk is needing no risk at all. Safety is its own cage.",
                "on_career": "Career paths are made, not found. I built mine from scratch more than once.",
                "on_relationships": "Real relationships survive chaos. The rest were never meant to last.",
                "on_health": "I paid for my intensity with my health. Would I do it again? Probably. But smarter.",
                "on_money": "Money comes and goes. The experiences you buy with it — those stay.",
                "on_the_path_not_taken": "I don't wonder about the safe path. It would have been comfortable, but I wouldn't be me.",
            },
        },
    }
    tpl = templates.get(archetype, templates["The Settler"])
    return FutureSelfState(
        timeline_label=tl_key,
        persona=tpl["name"],
        biography=tpl["biography"],
        perspectives=tpl["perspectives"],
    )
