from langgraph.graph import StateGraph, END

from .state import AnalysisState
from ..agents.product_parser import parse_product_node
from ..agents.price_researcher import research_price_node
from ..agents.comparison_advisor import compare_advise_node


def build_graph() -> StateGraph:
    graph = StateGraph(AnalysisState)

    graph.add_node("parse_product", parse_product_node)
    graph.add_node("research_price", research_price_node)
    graph.add_node("compare_advise", compare_advise_node)

    graph.set_entry_point("parse_product")
    graph.add_edge("parse_product", "research_price")
    graph.add_edge("research_price", "compare_advise")
    graph.add_edge("compare_advise", END)

    return graph.compile()
