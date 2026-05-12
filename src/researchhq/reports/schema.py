"""Schema for the unified research report and its inputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from researchhq.search.source_quality import RankedSource


class ResearchPlan(BaseModel):
    queries: list[str]
    rationale: str = ""


class Fact(BaseModel):
    claim: str
    evidence_urls: list[str] = Field(default_factory=list)
    confidence: float = 0.5  # 0.0 - 1.0


class Section(BaseModel):
    heading: str
    body: str


class FetchedPageSummary(BaseModel):
    url: str
    title: str
    status: int
    chars: int
    truncated: bool


class CitationViolation(BaseModel):
    kind: str
    location: str
    url: str = ""
    detail: str = ""


class RuleResult(BaseModel):
    name: str
    severity: Literal["info", "warn", "fail"]
    passed: bool
    message: str


class VerifierNote(BaseModel):
    overall_confidence: float
    notes: list[str] = Field(default_factory=list)
    rules: list[RuleResult] = Field(default_factory=list)
    violations: list[CitationViolation] = Field(default_factory=list)


class StageCost(BaseModel):
    stage: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    equivalent_paid_cost_usd: float = 0.0


class ResearchReport(BaseModel):
    mode: str
    query: str
    effort: str = "medium"
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    plan: ResearchPlan
    sources: list[RankedSource] = Field(default_factory=list)
    fetched_pages: list[FetchedPageSummary] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    sections: list[Section] = Field(default_factory=list)
    verifier: VerifierNote | None = None
    next_questions: list[str] = Field(default_factory=list)
    stage_costs: list[StageCost] = Field(default_factory=list)

    provider_used: str = ""
