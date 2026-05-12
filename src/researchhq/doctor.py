"""Health check: validates dependencies, configuration, providers, paths.

Run via `researchhq doctor` (or programmatically via `run_checks()`).
Returns a list of CheckResult with .ok and a short message.
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

CRITICAL = "critical"
WARN = "warn"
INFO = "info"

REQUIRED_DEPS = [
    ("typer", "CLI framework"),
    ("rich", "terminal rendering"),
    ("pydantic", "schema validation"),
    ("ddgs", "default search engine"),
    ("httpx", "HTTP client"),
    ("groq", "default LLM provider"),
    ("yaml", "config.yaml loader"),
]

OPTIONAL_DEPS = [
    ("PySide6", "GUI"),
    ("openai", "OpenAI provider (optional)"),
    ("anthropic", "Anthropic provider (optional)"),
    ("ollama", "local Ollama provider"),
    ("google.genai", "Gemini provider"),
]


@dataclass
class CheckResult:
    name: str
    ok: bool
    severity: str  # critical | warn | info
    message: str


def _check_python() -> CheckResult:
    v = sys.version_info
    ok = v >= (3, 11)
    return CheckResult(
        "Python version", ok, CRITICAL if not ok else INFO,
        f"{v.major}.{v.minor}.{v.micro} (need >=3.11)",
    )


def _check_required_deps() -> list[CheckResult]:
    out: list[CheckResult] = []
    for mod, why in REQUIRED_DEPS:
        try:
            importlib.import_module(mod)
            out.append(CheckResult(f"dep:{mod}", True, INFO, why))
        except Exception as e:  # noqa: BLE001
            out.append(CheckResult(f"dep:{mod}", False, CRITICAL,
                                   f"missing ({type(e).__name__}); {why}"))
    return out


def _check_optional_deps() -> list[CheckResult]:
    out: list[CheckResult] = []
    for mod, why in OPTIONAL_DEPS:
        try:
            importlib.import_module(mod)
            out.append(CheckResult(f"opt:{mod}", True, INFO, why))
        except Exception:  # noqa: BLE001
            out.append(CheckResult(f"opt:{mod}", False, WARN,
                                   f"not installed; {why} unavailable"))
    return out


def _check_provider_keys() -> CheckResult:
    from researchhq.config import settings
    keys = {
        "GROQ_API_KEY":      bool(settings.groq_api_key),
        "GEMINI_API_KEY":    bool(settings.gemini_api_key),
        "OPENAI_API_KEY":    bool(settings.openai_api_key),
        "ANTHROPIC_API_KEY": bool(settings.anthropic_api_key),
    }
    has_remote = any(keys.values())
    has_ollama = True  # always 'available' as a fallback path; may fail at call time
    set_keys = [k for k, v in keys.items() if v]
    if has_remote:
        return CheckResult("Provider keys", True, INFO,
                           f"configured: {', '.join(set_keys)} + ollama fallback")
    if has_ollama:
        return CheckResult("Provider keys", True, WARN,
                           "no remote API keys; relying on local Ollama (ensure it's running)")
    return CheckResult("Provider keys", False, CRITICAL,
                       "no providers configured. Set at least GROQ_API_KEY in .env")


def _check_output_folder() -> CheckResult:
    from researchhq.config import settings
    folder = Path(settings.output_folder)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=folder, delete=True):
            pass
        return CheckResult("Output folder writable", True, INFO, str(folder.resolve()))
    except Exception as e:  # noqa: BLE001
        return CheckResult("Output folder writable", False, CRITICAL,
                           f"cannot write to {folder}: {e}")


def _check_history_db() -> CheckResult:
    try:
        from researchhq.history import db_path, ensure_db
        ensure_db()
        return CheckResult("History DB", True, INFO, str(db_path()))
    except Exception as e:  # noqa: BLE001
        return CheckResult("History DB", False, WARN,
                           f"cannot initialize: {e}")


def _check_gui_import() -> CheckResult:
    try:
        importlib.import_module("PySide6.QtWidgets")
        return CheckResult("GUI importable", True, INFO,
                           "PySide6 present; `python -m researchhq.gui` should launch")
    except Exception:  # noqa: BLE001
        return CheckResult("GUI importable", False, WARN,
                           "PySide6 not installed (CLI works; install with `pip install -e \".[gui]\"`)")


def _check_router_loadable() -> CheckResult:
    """Confirm the router can construct a provider chain (no API call)."""
    try:
        from researchhq.llm.router import LLMRouter
        r = LLMRouter()
        names = [p.name for p in r.providers]
        if not names:
            return CheckResult("Router providers", False, CRITICAL,
                               "no providers initialized; check API keys / Ollama host")
        return CheckResult("Router providers", True, INFO,
                           f"chain: {' -> '.join(names)}")
    except Exception as e:  # noqa: BLE001
        return CheckResult("Router providers", False, CRITICAL, f"router init failed: {e}")


def run_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    results.append(_check_python())
    results.extend(_check_required_deps())
    results.append(_check_provider_keys())
    results.append(_check_router_loadable())
    results.append(_check_output_folder())
    results.append(_check_history_db())
    results.append(_check_gui_import())
    results.extend(_check_optional_deps())
    return results


def has_critical_failure(results: list[CheckResult]) -> bool:
    return any((not r.ok) and r.severity == CRITICAL for r in results)
