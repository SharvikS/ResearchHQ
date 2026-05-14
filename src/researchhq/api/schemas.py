"""Pydantic request/response schemas for the ResearchHQ REST API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Request models ─────────────────────────────────────────────────────────────

class QueryOptions(BaseModel):
    enable_web_search: bool = True
    enable_technical: bool = True
    max_pipelines: int = Field(default=4, ge=1, le=5)
    timeout_seconds: int = Field(default=90, ge=10, le=300)
    language: str = "en"
    ensemble_mode: Literal["cheap", "balanced", "max_confidence"] = "balanced"


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=4000)
    mode: Literal["general", "academic", "company", "competitor", "market", "news", "technology"] = "general"
    pipeline_mode: Literal["fast", "balanced", "deep"] = "balanced"
    format: Literal["markdown", "json", "plain"] = "markdown"
    options: QueryOptions = Field(default_factory=QueryOptions)


# ── Pipeline status models ─────────────────────────────────────────────────────

class PipelineStatus(BaseModel):
    slot_name: str
    display_name: str
    provider: str
    status: Literal["pending", "running", "complete", "failed", "timeout", "skipped"]
    latency_ms: Optional[int] = None
    error: Optional[str] = None


class QueryStatusResponse(BaseModel):
    query_id: str
    status: Literal["queued", "running", "complete", "failed", "partial"]
    progress_pct: int = 0
    pipelines: List[PipelineStatus] = []
    created_at: datetime
    updated_at: datetime
    error: Optional[str] = None


# ── Source / confidence models ─────────────────────────────────────────────────

class SourceRef(BaseModel):
    url: str
    title: str
    domain: str
    trust_score: float
    snippet: Optional[str] = None


class ConfidenceBreakdown(BaseModel):
    provider_agreement: float
    source_quality: float
    factual_consistency: float
    hallucination_safety: float


class ConfidenceResult(BaseModel):
    overall_score: float
    label: Literal["high", "medium", "low"]
    breakdown: ConfidenceBreakdown
    uncertainty_notes: List[str] = []


# ── Agent output model (expandable in UI) ─────────────────────────────────────

class AgentOutput(BaseModel):
    slot_name: str
    display_name: str
    provider: str
    model: str
    content: str
    status: str
    latency_ms: int
    input_tokens: int
    output_tokens: int


# ── Execution metadata ─────────────────────────────────────────────────────────

class ExecutionMetadata(BaseModel):
    total_latency_ms: int
    pipelines_run: int
    pipelines_failed: int
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float
    ensemble_mode: str
    provider_used: str


# ── Final response ─────────────────────────────────────────────────────────────

class FinalResponse(BaseModel):
    query_id: str
    status: str
    executive_summary: str
    detailed_answer: str
    key_findings: List[str]
    conflicting_viewpoints: List[str] = []
    limitations: List[str] = []
    confidence: ConfidenceResult
    sources: List[SourceRef] = []
    agent_outputs: Dict[str, AgentOutput] = {}
    execution_metadata: ExecutionMetadata
    created_at: datetime


class QueryResultResponse(BaseModel):
    query_id: str
    status: str
    final_response: Optional[FinalResponse] = None
    warnings: List[str] = []


# ── Agent info ─────────────────────────────────────────────────────────────────

class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    slot: str
    preferred_providers: List[str]


class AgentsResponse(BaseModel):
    agents: List[AgentInfo]
    pipeline_modes: Dict[str, List[str]]  # mode → slot names


# ── Logs ──────────────────────────────────────────────────────────────────────

class LogEntry(BaseModel):
    id: int
    query_id: str
    level: str
    stage: str
    message: str
    data: Optional[Dict[str, Any]] = None
    created_at: datetime


class LogsResponse(BaseModel):
    query_id: str
    logs: List[LogEntry]
    total: int


# ── Health ────────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    version: str
    providers_available: List[str]
    circuit_breakers_open: List[str] = Field(default_factory=list)
