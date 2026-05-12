from researchhq.modes.base import ResearchMode
from researchhq.modes.academic import AcademicMode
from researchhq.modes.company import CompanyMode
from researchhq.modes.competitor import CompetitorMode
from researchhq.modes.general import GeneralMode
from researchhq.modes.market import MarketMode
from researchhq.modes.news import NewsMode
from researchhq.modes.technology import TechnologyMode

MODES: dict[str, type[ResearchMode]] = {
    "topic": GeneralMode,
    "general": GeneralMode,
    "company": CompanyMode,
    "competitor": CompetitorMode,
    "tech": TechnologyMode,
    "technology": TechnologyMode,
    "market": MarketMode,
    "news": NewsMode,
    "academic": AcademicMode,
    "paper": AcademicMode,
}


def get_mode(name: str) -> ResearchMode:
    key = name.strip().lower()
    if key not in MODES:
        raise KeyError(
            f"Unknown research mode '{name}'. Available: {sorted(set(MODES))}"
        )
    return MODES[key]()


__all__ = ["MODES", "get_mode", "ResearchMode"]
