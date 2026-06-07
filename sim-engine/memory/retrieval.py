"""
Retrieval service — augments simulation context with relevant memories.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from memory.chroma_store import get_memory_store

logger = logging.getLogger(__name__)


def retrieve_context(decision: str, user_id: Optional[str] = None) -> dict:
    store = get_memory_store()
    similar = store.query_similar_decisions(decision, n_results=3)

    context = {
        "similar_simulations": [],
        "user_preferences": {},
        "historical_patterns": [],
    }

    for item in similar:
        meta = item.get("metadata", {})
        doc = item.get("document", "")
        if meta.get("type") == "simulation":
            try:
                parsed = json.loads(doc) if isinstance(doc, str) else doc
                context["similar_simulations"].append({
                    "decision": meta.get("decision", ""),
                    "result": parsed.get("result_summary", {}),
                    "similarity": 1 - item.get("distance", 0),
                })
            except (json.JSONDecodeError, TypeError):
                pass

    return context


def build_memory_prompt_block(decision: str, user_id: Optional[str] = None) -> str:
    context = retrieve_context(decision, user_id)
    if not context["similar_simulations"]:
        return "No previous similar simulations found."

    block_parts = ["PREVIOUS SIMULATION MEMORIES:"]
    for sim in context["similar_simulations"][:2]:
        block_parts.append(
            f"- Decision: {sim['decision'][:80]} | "
            f"Primary path: {sim['result'].get('primary_path', 'N/A')} | "
            f"Similarity: {sim.get('similarity', 0):.0%}"
        )
    return "\n".join(block_parts)
