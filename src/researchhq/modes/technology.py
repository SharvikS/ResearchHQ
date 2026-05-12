from researchhq.modes.base import ModeConfig, ReportSection, ResearchMode
from researchhq.search.source_quality import SourceTier


class TechnologyMode(ResearchMode):
    config = ModeConfig(
        name="technology",
        description="Technology / framework / platform research with emphasis on docs and code.",
        seed_query_templates=[
            "{q} documentation",
            "{q} architecture overview",
            "{q} github",
            "{q} use cases",
            "{q} alternatives comparison",
            "{q} deployment requirements",
            "{q} security considerations",
            "{q} tutorial getting started",
        ],
        preferred_tiers=[
            SourceTier.OFFICIAL, SourceTier.DOCS, SourceTier.GITHUB,
            SourceTier.ACADEMIC, SourceTier.NEWS,
        ],
        drop_tiers={SourceTier.SEARCH_ENGINE, SourceTier.LOW_QUALITY},
        tier_weights={SourceTier.DOCS: 10, SourceTier.GITHUB: 9, SourceTier.OFFICIAL: 11},
        report_sections=[
            ReportSection("Executive summary"),
            ReportSection("What it is"),
            ReportSection("Architecture and components"),
            ReportSection("Use cases"),
            ReportSection("Implementation notes"),
            ReportSection("Comparable technologies"),
            ReportSection("Recent developments", required=False),
            ReportSection("Risks and limitations"),
            ReportSection("Confidence score"),
            ReportSection("Sources"),
            ReportSection("Recommended next research questions"),
        ],
        confidence_rules=[
            "Prefer DOCS and OFFICIAL sources for capability claims.",
            "GITHUB metrics (stars, last commit) corroborate adoption signals only.",
        ],
        synthesizer_persona="You are a senior software engineer evaluating a technology for production use.",
    )

    def seed_queries(self, query: str) -> list[str]:
        return [t.format(q=query) for t in self.config.seed_query_templates]
