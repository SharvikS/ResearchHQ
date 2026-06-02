"""Layered config: YAML defaults <- .env / environment <- CLI flags."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load global user config (~/.researchhq/.env) first, then local .env overrides it.
_global_env = Path.home() / ".researchhq" / ".env"
if _global_env.exists():
    load_dotenv(_global_env)
load_dotenv(override=True)

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is in deps
    yaml = None  # type: ignore[assignment]


DEFAULT_YAML: dict[str, Any] = {
    "provider": {
        "default": "groq",
        "fallback_chain": ["groq", "gemini", "ollama"],
    },
    "models": {
        "groq": "llama-3.3-70b-versatile",
        "gemini": "gemini-2.0-flash-exp",
        "ollama": "llama3.2:3b",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-haiku-4-5-20251001",
    },
    "search": {
        "engines": ["duckduckgo"],
        "max_results_per_query": 6,
        "max_total_sources": 18,
    },
    "report": {
        "output_folder": "reports",
        "default_format": "markdown",
        "include_recent_developments": True,
    },
    "verbosity": {
        "default": "normal",
        "hide_http_logs_unless_debug": True,
    },
    "ensemble": {
        "enabled": False,
        "providers": [],           # empty → derived from mode profile
        "mode": "balanced",        # cheap | balanced | max_confidence
        "provider_timeout": 60.0,
        "max_parallel_providers": 5,
        "consensus_threshold": 0.35,
        "min_providers_consensus": 2,
        "use_llm_extraction": False,  # True only recommended for max_confidence
        "cost_optimize": True,
    },
}


@dataclass
class Settings:
    # API keys / hosts (read from env)
    groq_api_key: str = ""
    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    ollama_host: str = "http://localhost:11434"

    # YAML-driven config
    default_provider: str = "groq"
    fallback_chain: list[str] = field(default_factory=lambda: ["groq", "gemini", "ollama"])
    models: dict[str, str] = field(default_factory=dict)
    search_engines: list[str] = field(default_factory=lambda: ["duckduckgo"])
    max_results_per_query: int = 6
    max_total_sources: int = 18
    output_folder: str = "reports"
    default_format: str = "markdown"
    include_recent_developments: bool = True
    verbosity_default: str = "normal"
    hide_http_logs_unless_debug: bool = True

    log_level: str = "INFO"

    # Ensemble settings
    ensemble_enabled: bool = False
    ensemble_providers: list[str] = field(default_factory=list)
    ensemble_mode: str = "balanced"
    ensemble_provider_timeout: float = 60.0
    ensemble_max_parallel_providers: int = 5
    ensemble_consensus_threshold: float = 0.35
    ensemble_min_providers_consensus: int = 2
    ensemble_use_llm_extraction: bool = False
    ensemble_cost_optimize: bool = True


VALID_PROVIDERS = {"groq", "gemini", "ollama", "openai", "anthropic"}
VALID_FORMATS = {"markdown", "md", "json", "html"}
VALID_VERBOSITY = {"quiet", "normal", "verbose", "debug"}
VALID_ENSEMBLE_MODES = {"cheap", "balanced", "max_confidence"}


class ConfigError(ValueError):
    """Raised when ResearchHQ configuration is malformed."""


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_yaml_chain() -> dict[str, Any]:
    """Load YAML config: defaults <- global (~/.researchhq/config.yaml) <- local."""
    raw = dict(DEFAULT_YAML)
    if yaml is None:
        return raw

    def _try_merge(path: Path) -> None:
        try:
            with path.open("r", encoding="utf-8") as f:
                user = yaml.safe_load(f) or {}
            if not isinstance(user, dict):
                raise ConfigError(f"{path} must contain a YAML mapping at the top level.")
            raw.update(_deep_merge(raw, user))
        except ConfigError:
            raise
        except Exception as exc:
            raise ConfigError(f"Failed to read config file {path}: {exc}") from exc

    # 1. Global user config
    global_yaml = Path.home() / ".researchhq" / "config.yaml"
    if global_yaml.exists():
        _try_merge(global_yaml)

    # 2. Explicit override or local project config
    explicit = os.environ.get("RESEARCHHQ_CONFIG")
    if explicit:
        local = Path(explicit)
        if local.exists():
            _try_merge(local)
    else:
        for candidate in (Path("config.yaml"), Path("researchhq.yaml")):
            if candidate.exists():
                _try_merge(candidate)
                break

    return raw


def _require_section(raw: dict[str, Any], section: str) -> dict[str, Any]:
    value = raw.get(section)
    if not isinstance(value, dict):
        raise ConfigError(f"Config section '{section}' must be a mapping.")
    return value


def _as_str(value: Any, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"Config value '{key}' must be a non-empty string.")
    return value.strip()


def _as_str_list(value: Any, key: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise ConfigError(f"Config value '{key}' must be a list of non-empty strings.")
    out = [v.strip().lower() for v in value]
    if not allow_empty and not out:
        raise ConfigError(f"Config value '{key}' must include at least one item.")
    return out


def _as_int(value: Any, key: str, *, minimum: int, maximum: int) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Config value '{key}' must be an integer.") from exc
    if out < minimum or out > maximum:
        raise ConfigError(f"Config value '{key}' must be between {minimum} and {maximum}.")
    return out


def _as_float(value: Any, key: str, *, minimum: float, maximum: float) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Config value '{key}' must be a number.") from exc
    if out < minimum or out > maximum:
        raise ConfigError(f"Config value '{key}' must be between {minimum} and {maximum}.")
    return out


def _validate_raw(raw: dict[str, Any]) -> dict[str, Any]:
    provider = _require_section(raw, "provider")
    models = _require_section(raw, "models")
    search = _require_section(raw, "search")
    report = _require_section(raw, "report")
    verbosity = _require_section(raw, "verbosity")
    ensemble = _require_section(raw, "ensemble")

    default_provider = _as_str(provider.get("default"), "provider.default").lower()
    if default_provider not in VALID_PROVIDERS:
        raise ConfigError(f"provider.default must be one of {sorted(VALID_PROVIDERS)}.")

    fallback_chain = _as_str_list(provider.get("fallback_chain"), "provider.fallback_chain")
    invalid_fallbacks = sorted(set(fallback_chain) - VALID_PROVIDERS)
    if invalid_fallbacks:
        raise ConfigError(f"provider.fallback_chain contains unknown providers: {invalid_fallbacks}.")

    if not isinstance(models, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in models.items()):
        raise ConfigError("Config section 'models' must map provider names to model strings.")

    engines = _as_str_list(search.get("engines"), "search.engines")
    max_results = _as_int(search.get("max_results_per_query"), "search.max_results_per_query", minimum=1, maximum=25)
    max_sources = _as_int(search.get("max_total_sources"), "search.max_total_sources", minimum=1, maximum=100)

    output_folder = _as_str(report.get("output_folder"), "report.output_folder")
    default_format = _as_str(report.get("default_format"), "report.default_format").lower()
    if default_format not in VALID_FORMATS:
        raise ConfigError(f"report.default_format must be one of {sorted(VALID_FORMATS)}.")

    verbosity_default = _as_str(verbosity.get("default"), "verbosity.default").lower()
    if verbosity_default not in VALID_VERBOSITY:
        raise ConfigError(f"verbosity.default must be one of {sorted(VALID_VERBOSITY)}.")

    ensemble_mode = _as_str(ensemble.get("mode"), "ensemble.mode").lower()
    if ensemble_mode not in VALID_ENSEMBLE_MODES:
        raise ConfigError(f"ensemble.mode must be one of {sorted(VALID_ENSEMBLE_MODES)}.")

    ensemble_providers = _as_str_list(
        ensemble.get("providers", []),
        "ensemble.providers",
        allow_empty=True,
    )
    invalid_ensemble = sorted(set(ensemble_providers) - VALID_PROVIDERS)
    if invalid_ensemble:
        raise ConfigError(f"ensemble.providers contains unknown providers: {invalid_ensemble}.")

    provider["default"] = default_provider
    provider["fallback_chain"] = fallback_chain
    search["engines"] = engines
    search["max_results_per_query"] = max_results
    search["max_total_sources"] = max_sources
    report["output_folder"] = output_folder
    report["default_format"] = default_format
    verbosity["default"] = verbosity_default
    ensemble["providers"] = ensemble_providers
    ensemble["mode"] = ensemble_mode
    ensemble["provider_timeout"] = _as_float(ensemble.get("provider_timeout"), "ensemble.provider_timeout", minimum=1.0, maximum=600.0)
    ensemble["max_parallel_providers"] = _as_int(ensemble.get("max_parallel_providers"), "ensemble.max_parallel_providers", minimum=1, maximum=10)
    ensemble["consensus_threshold"] = _as_float(ensemble.get("consensus_threshold"), "ensemble.consensus_threshold", minimum=0.0, maximum=1.0)
    ensemble["min_providers_consensus"] = _as_int(ensemble.get("min_providers_consensus"), "ensemble.min_providers_consensus", minimum=1, maximum=10)

    return raw


def load_settings() -> Settings:
    raw = _validate_raw(_load_yaml_chain())

    s = Settings(
        groq_api_key=os.environ.get("GROQ_API_KEY", ""),
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        default_provider=raw["provider"]["default"],
        fallback_chain=list(raw["provider"]["fallback_chain"]),
        models=dict(raw["models"]),
        search_engines=list(raw["search"]["engines"]),
        max_results_per_query=int(raw["search"]["max_results_per_query"]),
        max_total_sources=int(raw["search"]["max_total_sources"]),
        output_folder=raw["report"]["output_folder"],
        default_format=raw["report"]["default_format"],
        include_recent_developments=bool(raw["report"]["include_recent_developments"]),
        verbosity_default=raw["verbosity"]["default"],
        hide_http_logs_unless_debug=bool(raw["verbosity"]["hide_http_logs_unless_debug"]),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        # Ensemble
        ensemble_enabled=bool(
            raw.get("ensemble", {}).get("enabled", False)
            or os.environ.get("ENSEMBLE_ENABLED", "").lower() in ("1", "true", "yes")
        ),
        ensemble_providers=list(raw.get("ensemble", {}).get("providers", [])),
        ensemble_mode=str(raw.get("ensemble", {}).get("mode", "balanced")),
        ensemble_provider_timeout=float(raw.get("ensemble", {}).get("provider_timeout", 60.0)),
        ensemble_max_parallel_providers=int(raw.get("ensemble", {}).get("max_parallel_providers", 5)),
        ensemble_consensus_threshold=float(raw.get("ensemble", {}).get("consensus_threshold", 0.35)),
        ensemble_min_providers_consensus=int(raw.get("ensemble", {}).get("min_providers_consensus", 2)),
        ensemble_use_llm_extraction=bool(raw.get("ensemble", {}).get("use_llm_extraction", False)),
        ensemble_cost_optimize=bool(raw.get("ensemble", {}).get("cost_optimize", True)),
    )
    return s


settings = load_settings()


# --- Live config edits (used by the TUI Settings screen) --------------------

def save_settings(updates: dict[str, Any], path: Path | None = None) -> Path:
    """Merge `updates` into `config.yaml` on disk and return the file path.

    `updates` is a flat dict of { settings_field: value }. Keys are mapped
    back to their YAML section automatically.
    """
    if yaml is None:
        raise RuntimeError("PyYAML is required to persist settings.")

    default_path = Path.home() / ".researchhq" / "config.yaml"
    target = path or default_path
    current: dict[str, Any] = {}
    if target.exists():
        with target.open("r", encoding="utf-8") as f:
            current = yaml.safe_load(f) or {}

    section_for = {
        "default_provider":   ("provider", "default"),
        "fallback_chain":     ("provider", "fallback_chain"),
        "models":             ("models", None),
        "search_engines":     ("search", "engines"),
        "max_results_per_query": ("search", "max_results_per_query"),
        "max_total_sources":  ("search", "max_total_sources"),
        "output_folder":      ("report", "output_folder"),
        "default_format":     ("report", "default_format"),
        "include_recent_developments": ("report", "include_recent_developments"),
        "verbosity_default":  ("verbosity", "default"),
        "ensemble_enabled":              ("ensemble", "enabled"),
        "ensemble_providers":            ("ensemble", "providers"),
        "ensemble_mode":                 ("ensemble", "mode"),
        "ensemble_provider_timeout":     ("ensemble", "provider_timeout"),
        "ensemble_max_parallel_providers": ("ensemble", "max_parallel_providers"),
        "ensemble_consensus_threshold":  ("ensemble", "consensus_threshold"),
        "ensemble_min_providers_consensus": ("ensemble", "min_providers_consensus"),
        "ensemble_use_llm_extraction":   ("ensemble", "use_llm_extraction"),
        "ensemble_cost_optimize":        ("ensemble", "cost_optimize"),
    }
    for k, v in updates.items():
        section_key = section_for.get(k)
        if not section_key:
            continue
        section, leaf = section_key
        if leaf is None:
            current[section] = v
        else:
            current.setdefault(section, {})
            current[section][leaf] = v

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        yaml.safe_dump(current, f, sort_keys=False, default_flow_style=False)
    return target


def reload_settings() -> Settings:
    """Re-read config from disk, mutate the global `settings` in place so any
    code that imported the singleton picks up the new values."""
    new_s = load_settings()
    for k in vars(new_s):
        setattr(settings, k, getattr(new_s, k))
    return settings
