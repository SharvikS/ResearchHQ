"""Persist multi-agent runs to disk so `sources` and `export` can reuse them."""

import json
from pathlib import Path
from typing import Any

REPORTS_DIR = Path("reports")


def slugify(name: str) -> str:
    cleaned = "".join(c.lower() if c.isalnum() else "_" for c in name).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned or "unnamed"


def _md_path(company: str) -> Path:
    return REPORTS_DIR / f"{slugify(company)}.md"


def _json_path(company: str) -> Path:
    return REPORTS_DIR / f"{slugify(company)}.json"


def save_run(state: dict[str, Any]) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(exist_ok=True)
    company = state["company"]
    md = _md_path(company)
    js = _json_path(company)

    md.write_text(state["final_report"], encoding="utf-8")

    payload = {
        "company": company,
        "final_report": state["final_report"],
        "synthesis_provider": state.get("synthesis_provider", ""),
        "findings": [f.model_dump(mode="json") for f in state.get("findings", [])],
    }
    js.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return md, js


def load_run(company: str) -> dict[str, Any] | None:
    js = _json_path(company)
    if not js.exists():
        return None
    return json.loads(js.read_text(encoding="utf-8"))


def briefing_path(company: str) -> Path:
    return _md_path(company)
