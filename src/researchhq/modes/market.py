from researchhq.modes.base import ModeConfig, ReportSection, ResearchMode
from researchhq.search.source_quality import SourceTier


class MarketMode(ResearchMode):
    config = ModeConfig(
        name="market",
        description="Industry / market sizing, trends, leaders, and dynamics.",
        seed_query_templates=[
            "{q} market size 2026",
            "{q} market growth forecast",
            "{q} key players leaders",
            "{q} industry report",
            "{q} segments breakdown",
            "{q} trends drivers",
            "{q} regulations risks",
            "{q} acquisitions M&A 2026",
        ],
        preferred_tiers=[
            SourceTier.NEWS, SourceTier.GOVERNMENT, SourceTier.COMPARISON,
            SourceTier.OFFICIAL, SourceTier.ACADEMIC,
        ],
        drop_tiers={SourceTier.SEARCH_ENGINE, SourceTier.LOW_QUALITY, SourceTier.SOCIAL},
        tier_weights={SourceTier.NEWS: 10, SourceTier.GOVERNMENT: 11},
        report_sections=[
            ReportSection("Executive summary"),
            ReportSection("Market overview and size"),
            ReportSection("Key players"),
            ReportSection("Segments and dynamics"),
            ReportSection("Trends and drivers"),
            ReportSection("Recent developments"),
            ReportSection("Risks and limitations"),
            ReportSection("Confidence score"),
            ReportSection("Sources"),
            ReportSection("Recommended next research questions"),
        ],
        confidence_rules=[
            "Market size figures must cite a dated, attributable source. Otherwise mark as 'reported, unverified'.",
            "Confidence drops when only one analyst firm is cited.",
        ],
        synthesizer_persona="You are a market analyst preparing a briefing for an executive audience.",
    )

    def seed_queries(self, query: str) -> list[str]:
        return [t.format(q=query) for t in self.config.seed_query_templates]
