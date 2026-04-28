"""
Letter Agent — thin wrapper around the batch synthesis result.

The actual LLM call (if any) is made by batch_synthesis() in synthesis.py.
"""
from agents.synthesis import get_synthesis_store


def write_future_letter(timeline: dict, regret: dict, timeline_key: str = "") -> str:
    """
    Return the future-self letter for a single timeline.
    Reads from the synthesis store; falls back to a template letter.
    """
    store = get_synthesis_store()
    if store and timeline_key:
        letter = store.get("letters", {}).get(timeline_key)
        if letter:
            return letter

    return _template_letter(timeline, regret)


def _template_letter(timeline: dict, regret: dict) -> str:
    years = [v for k, v in timeline.items() if k.startswith("Year") and isinstance(v, str)]
    year10 = years[-1] if years else "Your life has unfolded in ways you didn't expect."
    opp    = regret.get("lost_opportunity", "other paths")
    cost   = regret.get("emotional_cost", "the weight of your choices")

    return (
        f"Dear you,\n\n"
        f"It's been ten years. {year10}\n\n"
        f"There were moments I thought about {opp} — "
        f"and {cost} stayed with me longer than I expected.\n\n"
        f"What I wish I'd known: the early years are harder than the numbers suggest. "
        f"The salary figures are real, but so is the gap between what you earn and what "
        f"you feel you deserve. Close that gap slowly — it doesn't close overnight.\n\n"
        f"The one thing I'd tell you: make the decision you can explain to yourself "
        f"five years from now. Not to anyone else. Just yourself.\n\n"
        f"You'll be okay.\n\n"
        f"— You, ten years from now"
    )
