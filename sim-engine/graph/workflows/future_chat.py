"""
Future Self Chat workflow — enables conversation with timeline personas.
"""
import json
import logging
from typing import Any, Dict, List, Optional

from graph.state import FutureChatState, FutureSelfState

logger = logging.getLogger(__name__)


def run_future_chat(
    timeline_label: str,
    user_question: str,
    future_self_persona: dict,
    timeline_data: dict,
    conversation_history: Optional[List[dict]] = None,
) -> str:
    from graph.agents.future_self import FutureChatAgent

    agent = FutureChatAgent()
    response = agent.chat(
        persona=future_self_persona,
        timeline_data=timeline_data,
        question=user_question,
        conversation_history=conversation_history,
    )
    return response
