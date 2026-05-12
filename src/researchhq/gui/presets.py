"""Built-in research presets. A preset just pre-fills the research form."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Preset:
    name: str
    mode: str
    placeholder: str
    description: str
    max_sources: int = 18
    template: str = "{q}"   # how user input is rendered into the final query


PRESETS: list[Preset] = [
    Preset("Company deep dive", "company",
           placeholder="e.g. Supabase",
           description="Full company profile: product, pricing, market, momentum.",
           max_sources=24),
    Preset("Competitor comparison", "competitor",
           placeholder="e.g. Linear",
           description="Direct competitors, differentiation, community sentiment.",
           max_sources=22),
    Preset("Technology explainer", "technology",
           placeholder="e.g. MISP threat intelligence platform",
           description="Architecture, use cases, alternatives, deployment notes.",
           max_sources=18),
    Preset("Market landscape", "market",
           placeholder="e.g. Backend-as-a-Service market",
           description="Market size, players, segments, trends, recent M&A.",
           max_sources=20),
    Preset("Latest news scan", "news",
           placeholder="e.g. OpenAI latest product updates",
           description="Recent developments with multi-source corroboration.",
           max_sources=18),
    Preset("Academic literature scan", "academic",
           placeholder="e.g. retrieval augmented generation evaluation",
           description="Survey of key papers, methods, open problems.",
           max_sources=18),
    Preset("Product review analysis", "topic",
           placeholder="e.g. Logitech MX Master 3S review",
           description="What real users actually think across forums and review sites.",
           max_sources=18,
           template="{q} review pros cons community feedback"),
]
