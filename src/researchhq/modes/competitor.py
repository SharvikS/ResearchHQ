from researchhq.modes.base import ModeConfig, ReportSection, ResearchMode
from researchhq.search.source_quality import SourceTier


class CompetitorMode(ResearchMode):
    config = ModeConfig(
        name="competitor",
        description="Competitive landscape around a target company.",
        seed_query_templates=[
            "{q} competitors comparison",
            "{q} alternatives to",
            "{q} vs review",
            "{q} pricing comparison",
            "{q} market share competitors",
            "{q} reddit discussion alternatives",
            "{q} g2 capterra reviews",
            "{q} latest product launch competitors",
        ],
        preferred_tiers=[
            SourceTier.COMPARISON, SourceTier.OFFICIAL, SourceTier.NEWS,
            SourceTier.COMMUNITY, SourceTier.DOCS,
        ],
        drop_tiers={SourceTier.SEARCH_ENGINE, SourceTier.LOW_QUALITY},
        tier_weights={SourceTier.COMPARISON: 10, SourceTier.COMMUNITY: 7},
        report_sections=[
            ReportSection("Executive summary"),
            ReportSection("Direct competitors"),
            ReportSection("Differentiation matrix"),
            ReportSection("Community sentiment"),
            ReportSection("Recent developments"),
            ReportSection("Strategic gaps and opportunities"),
            ReportSection("Risks and limitations"),
            ReportSection("Confidence score"),
            ReportSection("Sources"),
            ReportSection("Recommended next research questions"),
        ],
        confidence_rules=[
            "Each named competitor must be backed by at least one COMPARISON, NEWS or OFFICIAL source.",
            "Mark differentiation cells unknown when sources don't directly support them.",
        ],
        synthesizer_persona="You are a competitive intelligence analyst writing for a SaaS founder or PM.",
    )

    def seed_queries(self, query: str) -> list[str]:
        return [t.format(q=query) for t in self.config.seed_query_templates]
