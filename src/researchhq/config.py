"""Layered config: YAML defaults <- .env / environment <- CLI flags."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

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


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _find_yaml() -> Path | None:
    explicit = os.environ.get("RESEARCHHQ_CONFIG")
    if explicit:
        p = Path(explicit)
        return p if p.exists() else None
    for candidate in (Path("config.yaml"), Path("researchhq.yaml")):
        if candidate.exists():
            return candidate
    return None


def load_settings() -> Settings:
    raw = dict(DEFAULT_YAML)
    yaml_path = _find_yaml()
    if yaml_path and yaml is not None:
        try:
            with yaml_path.open("r", encoding="utf-8") as f:
                user = yaml.safe_load(f) or {}
            raw = _deep_merge(raw, user)
        except Exception:
            # Bad YAML: fall back to defaults silently; CLI --debug will show traces.
            pass

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

    target = path or _find_yaml() or Path("config.yaml")
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


def reload_settings() -> "Settings":
    """Re-read config from disk, mutate the global `settings` in place so any
    code that imported the singleton picks up the new values."""
    new_s = load_settings()
    for k in vars(new_s):
        setattr(settings, k, getattr(new_s, k))
    return settings
