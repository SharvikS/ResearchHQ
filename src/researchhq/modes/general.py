from researchhq.modes.base import ModeConfig, ReportSection, ResearchMode
from researchhq.search.source_quality import SourceTier


class GeneralMode(ResearchMode):
    config = ModeConfig(
        name="topic",
        description="General-purpose research on any topic, idea, trend, or person.",
        seed_query_templates=[
            "{q} overview",
            "{q} introduction explained",
            "{q} key concepts",
            "{q} latest developments",
            "{q} criticisms limitations",
            "{q} examples case studies",
        ],
        preferred_tiers=[
            SourceTier.OFFICIAL, SourceTier.ACADEMIC, SourceTier.GOVERNMENT,
            SourceTier.NEWS, SourceTier.DOCS, SourceTier.WIKI,
        ],
        drop_tiers={SourceTier.SEARCH_ENGINE, SourceTier.LOW_QUALITY},
        report_sections=[
            ReportSection("Executive summary"),
            ReportSection("Key findings"),
            ReportSection("Source-backed evidence"),
            ReportSection("Recent developments", required=False),
            ReportSection("Risks and limitations"),
            ReportSection("Confidence score"),
            ReportSection("Sources"),
            ReportSection("Recommended next research questions"),
        ],
        confidence_rules=[
            "Lower confidence when fewer than 3 high-tier (OFFICIAL/ACADEMIC/GOVERNMENT/NEWS) sources are present.",
            "Lower confidence if all evidence comes from a single domain.",
        ],
        synthesizer_persona="You are a senior research analyst writing a balanced, evidence-grounded brief.",
    )

    def seed_queries(self, query: str) -> list[str]:
        return [t.format(q=query) for t in self.config.seed_query_templates]
