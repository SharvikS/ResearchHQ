from researchhq.modes import MODES, get_mode
from researchhq.modes.base import ResearchMode


def test_all_advertised_modes_resolvable():
    for name in ["topic", "company", "competitor", "tech", "technology", "market", "news", "academic", "paper", "general"]:
        mode = get_mode(name)
        assert isinstance(mode, ResearchMode)
        assert mode.config.name
        assert mode.seed_queries("X")  # produces queries


def test_unknown_mode_raises():
    try:
        get_mode("notarealmode")
    except KeyError as e:
        assert "notarealmode" in str(e)
    else:
        raise AssertionError("get_mode should reject unknown modes")


def test_mode_aliases_share_class():
    assert MODES["tech"] is MODES["technology"]
    assert MODES["paper"] is MODES["academic"]
    assert MODES["general"] is MODES["topic"]
