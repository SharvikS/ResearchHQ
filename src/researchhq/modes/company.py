from researchhq.modes.base import ModeConfig, ReportSection, ResearchMode
from researchhq.search.source_quality import SourceTier


class CompanyMode(ResearchMode):
    config = ModeConfig(
        name="company",
        description="Deep profile of a specific company: business, product, market, momentum.",
        seed_query_templates=[
            "{q} company overview",
            "{q} products services",
            "{q} pricing plans",
            "{q} customers case studies",
            "{q} funding investors",
            "{q} leadership team",
            "{q} latest news 2026",
            "{q} competitors comparison",
        ],
        preferred_tiers=[
            SourceTier.OFFICIAL, SourceTier.NEWS, SourceTier.COMPARISON,
            SourceTier.DOCS, SourceTier.WIKI,
        ],
        drop_tiers={SourceTier.SEARCH_ENGINE, SourceTier.LOW_QUALITY},
        tier_weights={SourceTier.OFFICIAL: 11, SourceTier.NEWS: 9, SourceTier.COMPARISON: 8},
        report_sections=[
            ReportSection("Executive summary"),
            ReportSection("Company snapshot"),
            ReportSection("Products and pricing"),
            ReportSection("Market position"),
            ReportSection("Recent developments"),
            ReportSection("Risks and limitations"),
            ReportSection("Confidence score"),
            ReportSection("Sources"),
            ReportSection("Recommended next research questions"),
        ],
        confidence_rules=[
            "Confidence is HIGH only when official sources confirm key claims (pricing, product, leadership).",
            "Reduce confidence when relying primarily on third-party comparison sites.",
        ],
        synthesizer_persona="You are a senior business analyst profiling a company for an investor or operator.",
    )

    def seed_queries(self, query: str) -> list[str]:
        return [t.format(q=query) for t in self.config.seed_query_templates]
