from operator import add
from typing import Annotated, TypedDict

from pydantic import BaseModel

from competiq.sources import ClassifiedSource


class ResearchPlan(BaseModel):
    market_queries: list[str]
    signal_queries: list[str]
    news_queries: list[str]


class AgentFinding(BaseModel):
    agent: str
    summary: str
    sources: list[ClassifiedSource]
    queries: list[str]
    elapsed_seconds: float
    provider: str


class ResearchState(TypedDict):
    company: str
    plan: ResearchPlan | None
    findings: Annotated[list[AgentFinding], add]
    final_report: str
    synthesis_provider: str
