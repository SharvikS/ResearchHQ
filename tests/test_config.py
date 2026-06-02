from __future__ import annotations

import pytest

from researchhq.config import DEFAULT_YAML, ConfigError, _validate_raw


def test_config_validation_accepts_defaults() -> None:
    raw = _validate_raw(DEFAULT_YAML.copy())
    assert raw["provider"]["default"] == "groq"
    assert raw["report"]["default_format"] == "markdown"


def test_config_validation_rejects_unknown_provider() -> None:
    raw = DEFAULT_YAML.copy()
    raw["provider"] = dict(raw["provider"], default="mystery")
    with pytest.raises(ConfigError, match="provider.default"):
        _validate_raw(raw)


def test_config_validation_rejects_bad_numeric_limits() -> None:
    raw = DEFAULT_YAML.copy()
    raw["search"] = dict(raw["search"], max_total_sources=0)
    with pytest.raises(ConfigError, match="max_total_sources"):
        _validate_raw(raw)

