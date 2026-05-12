from researchhq.modes.base import ModeConfig, ReportSection, ResearchMode
from researchhq.search.source_quality import SourceTier


class AcademicMode(ResearchMode):
    config = ModeConfig(
        name="academic",
        description="Academic / research-paper investigation across a research area or paper.",
        seed_query_templates=[
            "{q} arxiv",
            "{q} survey paper",
            "{q} benchmark evaluation",
            "{q} literature review",
            "{q} state of the art",
            "{q} methodology",
            "{q} dataset",
            "{q} citation",
        ],
        preferred_tiers=[
            SourceTier.ACADEMIC, SourceTier.GOVERNMENT, SourceTier.DOCS,
            SourceTier.OFFICIAL, SourceTier.GITHUB,
        ],
        drop_tiers={SourceTier.SEARCH_ENGINE, SourceTier.LOW_QUALITY, SourceTier.SOCIAL, SourceTier.BLOG},
        tier_weights={SourceTier.ACADEMIC: 12, SourceTier.GOVERNMENT: 10},
        report_sections=[
            ReportSection("Executive summary"),
            ReportSection("Background and definitions"),
            ReportSection("Key papers and findings"),
            ReportSection("Methodologies"),
            ReportSection("Open problems"),
            ReportSection("Recent developments", required=False),
            ReportSection("Risks and limitations"),
            ReportSection("Confidence score"),
            ReportSection("Sources"),
            ReportSection("Recommended next research questions"),
        ],
        confidence_rules=[
            "Confidence only HIGH when claims trace to peer-reviewed or arxiv papers.",
            "Cite papers by title and authors when possible; venue and year when visible.",
        ],
        synthesizer_persona="You are a research scientist surveying the literature on a topic.",
    )

    def seed_queries(self, query: str) -> list[str]:
        return [t.format(q=query) for t in self.config.seed_query_templates]
