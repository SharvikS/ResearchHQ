import logging

from langgraph.graph import END, START, StateGraph

from competiq.agents.market import run_market_agent
from competiq.agents.news import run_news_agent
from competiq.agents.planner import plan_research
from competiq.agents.signal import run_signal_agent
from competiq.agents.synthesizer import synthesize
from competiq.graph.state import ResearchState

logger = logging.getLogger(__name__)


async def planner_node(state: ResearchState) -> dict:
    plan = await plan_research(state["company"])
    return {"plan": plan}


async def market_node(state: ResearchState) -> dict:
    finding = await run_market_agent(state["company"], state["plan"].market_queries)
    return {"findings": [finding]}


async def signal_node(state: ResearchState) -> dict:
    finding = await run_signal_agent(state["company"], state["plan"].signal_queries)
    return {"findings": [finding]}


async def news_node(state: ResearchState) -> dict:
    finding = await run_news_agent(state["company"], state["plan"].news_queries)
    return {"findings": [finding]}


async def synthesizer_node(state: ResearchState) -> dict:
    report, provider = await synthesize(state["company"], state["findings"])
    return {"final_report": report, "synthesis_provider": provider}


def build_graph():
    builder = StateGraph(ResearchState)
    builder.add_node("planner", planner_node)
    builder.add_node("market", market_node)
    builder.add_node("signal", signal_node)
    builder.add_node("news", news_node)
    builder.add_node("synthesizer", synthesizer_node)

    builder.add_edge(START, "planner")
    # Fan-out: 3 workers in parallel
    builder.add_edge("planner", "market")
    builder.add_edge("planner", "signal")
    builder.add_edge("planner", "news")
    # Fan-in: synthesizer waits for all three
    builder.add_edge("market", "synthesizer")
    builder.add_edge("signal", "synthesizer")
    builder.add_edge("news", "synthesizer")
    builder.add_edge("synthesizer", END)

    return builder.compile()


graph = build_graph()
