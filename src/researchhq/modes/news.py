from researchhq.modes.base import ModeConfig, ReportSection, ResearchMode
from researchhq.search.source_quality import SourceTier


class NewsMode(ResearchMode):
    config = ModeConfig(
        name="news",
        description="Recent / breaking developments around a topic, person, or organization.",
        seed_query_templates=[
            "{q} latest news",
            "{q} announcement 2026",
            "{q} recent updates this week",
            "{q} press release",
            "{q} this month launch",
            "{q} controversy reaction",
        ],
        preferred_tiers=[SourceTier.NEWS, SourceTier.OFFICIAL, SourceTier.GOVERNMENT],
        drop_tiers={SourceTier.SEARCH_ENGINE, SourceTier.LOW_QUALITY},
        tier_weights={SourceTier.NEWS: 11, SourceTier.OFFICIAL: 10},
        report_sections=[
            ReportSection("Executive summary"),
            ReportSection("Timeline of developments"),
            ReportSection("Key facts"),
            ReportSection("Reactions and analysis"),
            ReportSection("Risks and limitations"),
            ReportSection("Confidence score"),
            ReportSection("Sources"),
            ReportSection("Recommended next research questions"),
        ],
        confidence_rules=[
            "Confidence requires multiple independent NEWS sources confirming the same event.",
            "Single-source claims must be flagged 'unconfirmed'.",
        ],
        synthesizer_persona="You are a news analyst summarizing breaking developments for an executive audience.",
    )

    def seed_queries(self, query: str) -> list[str]:
        return [t.format(q=query) for t in self.config.seed_query_templates]
