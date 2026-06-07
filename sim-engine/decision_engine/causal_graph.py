from __future__ import annotations
from typing import Any, Dict, List
from .types import CausalGraph, CausalEdge, SIMULATION_YEARS


NODES = ["income", "career_growth", "stress", "health", "relationships", "happiness", "opportunity"]


def build_causal_graph(timelines: Dict[str, Any]) -> CausalGraph:
    edges = []
    positive_loops = []
    negative_loops = []

    causal_links = [
        ("income", "happiness", 0.35, "positive", "Higher income enables greater life satisfaction and financial freedom"),
        ("career_growth", "income", 0.6, "positive", "Career advancement drives salary growth and promotion-based raises"),
        ("career_growth", "opportunity", 0.5, "positive", "Career success opens doors to new opportunities and networks"),
        ("health", "happiness", 0.4, "positive", "Good health is a fundamental pillar of well-being and life satisfaction"),
        ("relationships", "happiness", 0.45, "positive", "Strong relationships provide emotional support and shared experiences"),
        ("stress", "health", -0.5, "negative", "Chronic stress degrades physical and mental health over time"),
        ("stress", "happiness", -0.3, "negative", "High stress directly reduces enjoyment and life satisfaction"),
        ("opportunity", "income", 0.25, "positive", "More opportunities lead to better-paying roles and side income"),
        ("income", "health", 0.15, "positive", "Financial resources enable better healthcare, nutrition, and wellness"),
        ("happiness", "relationships", 0.2, "positive", "Happier people attract and maintain stronger social connections"),
        ("career_growth", "stress", 0.3, "negative", "Career ambition often comes with increased pressure and workload"),
        ("income", "stress", -0.15, "positive", "Financial security reduces stress while wealth management adds complexity"),
    ]

    for src, tgt, strength, etype, desc in causal_links:
        edges.append(CausalEdge(
            source=src,
            target=tgt,
            strength=strength,
            effect_type=etype,
            description=desc,
        ))

    positive_loops = [
        ["career_growth", "income", "happiness", "relationships", "career_growth"],
        ["opportunity", "income", "health", "happiness", "opportunity"],
    ]
    negative_loops = [
        ["career_growth", "stress", "health", "happiness", "career_growth"],
        ["stress", "health", "happiness", "relationships", "stress"],
    ]

    return CausalGraph(
        nodes=NODES,
        edges=edges,
        positive_loops=positive_loops,
        negative_loops=negative_loops,
    )
