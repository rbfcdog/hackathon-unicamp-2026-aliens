from langgraph.graph import END, START, StateGraph

from app.graph.nodes import (
    apply_policy,
    assess_evidence,
    estimate_risk,
    explain_recommendation,
    extract_model_inputs,
    prepare_defense,
    price_agreement,
    request_human_review,
    route_recommendation,
)
from app.graph.state import AnalysisState


def build_analysis_graph():
    builder = StateGraph(AnalysisState)
    builder.add_node("extract_model_inputs", extract_model_inputs)
    builder.add_node("assess_evidence", assess_evidence)
    builder.add_node("estimate_risk", estimate_risk)
    builder.add_node("apply_policy", apply_policy)
    builder.add_node("price_agreement", price_agreement)
    builder.add_node("prepare_defense", prepare_defense)
    builder.add_node("request_human_review", request_human_review)
    builder.add_node("explain_recommendation", explain_recommendation)

    builder.add_edge(START, "extract_model_inputs")
    builder.add_edge("extract_model_inputs", "assess_evidence")
    builder.add_edge("assess_evidence", "estimate_risk")
    builder.add_edge("estimate_risk", "apply_policy")
    builder.add_conditional_edges(
        "apply_policy",
        route_recommendation,
        {
            "price_agreement": "price_agreement",
            "prepare_defense": "prepare_defense",
            "request_human_review": "request_human_review",
        },
    )
    builder.add_edge("price_agreement", "explain_recommendation")
    builder.add_edge("prepare_defense", "explain_recommendation")
    builder.add_edge("request_human_review", "explain_recommendation")
    builder.add_edge("explain_recommendation", END)
    return builder.compile()


analysis_graph = build_analysis_graph()
