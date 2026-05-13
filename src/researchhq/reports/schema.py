"""Schema for the unified research report and its inputs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

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


class EnsembleProviderSummary(BaseModel):
    provider: str
    model: str = ""
    status: str = "success"
    elapsed: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    error: Optional[str] = None


class EnsembleReportSection(BaseModel):
    """Serialisable summary of the ensemble run, attached to ResearchReport."""
    enabled: bool = True
    ensemble_mode: str = "balanced"
    providers_attempted: list[str] = Field(default_factory=list)
    providers_succeeded: list[str] = Field(default_factory=list)
    providers_failed: list[str] = Field(default_factory=list)
    provider_summaries: list[EnsembleProviderSummary] = Field(default_factory=list)
    # Consensus stats
    consensus_groups: int = 0
    contested_groups: int = 0
    unique_groups: int = 0
    overall_agreement_rate: float = 0.0
    # Confidence breakdown
    overall_confidence: float = 0.0
    adjusted_confidence: float = 0.0
    provider_agreement_score: float = 0.0
    source_quality_score: float = 0.0
    factual_consistency_score: float = 0.0
    hallucination_risk: float = 0.0
    confidence_label: str = "medium"
    support_strength: str = "medium"
    # Disagreements
    total_disagreements: int = 0
    major_disagreements: int = 0
    disagreement_summary: str = ""
    # Misc
    total_elapsed: float = 0.0
    uncertainty_notes: list[str] = Field(default_factory=list)
    provider_scores: dict[str, float] = Field(default_factory=dict)


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
    ensemble: Optional[EnsembleReportSection] = None
