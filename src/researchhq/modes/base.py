"""Mode protocol — every research mode declares its planning, source, and output strategy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from researchhq.search.source_quality import SourceTier


@dataclass
class ReportSection:
    heading: str
    required: bool = True
    description: str = ""


@dataclass
class ModeConfig:
    name: str
    description: str
    seed_query_templates: list[str] = field(default_factory=list)
    preferred_tiers: list[SourceTier] = field(default_factory=list)
    drop_tiers: set[SourceTier] = field(default_factory=set)
    tier_weights: dict[SourceTier, int] = field(default_factory=dict)
    report_sections: list[ReportSection] = field(default_factory=list)
    confidence_rules: list[str] = field(default_factory=list)
    synthesizer_persona: str = ""


class ResearchMode(ABC):
    """All seven concrete modes implement this."""

    config: ModeConfig

    @abstractmethod
    def seed_queries(self, query: str) -> list[str]: ...

    def report_skeleton(self) -> list[ReportSection]:
        return list(self.config.report_sections)

    @property
    def name(self) -> str:
        return self.config.name
