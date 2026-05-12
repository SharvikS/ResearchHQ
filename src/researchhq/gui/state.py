"""GUI-side state helpers: report discovery + persisted user preferences."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from researchhq.config import settings


@dataclass
class ReportSummary:
    path: Path
    mode: str
    query: str
    generated_at: str
    confidence: float | None = None
    sources_count: int = 0


def reports_dir() -> Path:
    return Path(settings.output_folder)


def list_reports() -> list[ReportSummary]:
    """Scan the output folder for previously saved JSON reports."""
    folder = reports_dir()
    if not folder.exists():
        return []
    out: list[ReportSummary] = []
    for p in sorted(folder.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        verifier = data.get("verifier") or {}
        out.append(
            ReportSummary(
                path=p,
                mode=data.get("mode", "?"),
                query=data.get("query", p.stem),
                generated_at=data.get("generated_at", ""),
                confidence=verifier.get("overall_confidence"),
                sources_count=len(data.get("sources", [])),
            )
        )
    return out


def load_report(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def delete_report(path: Path) -> None:
    """Delete the JSON file and any same-stem siblings (.md, .html)."""
    for ext in (".json", ".md", ".html"):
        sib = path.with_suffix(ext)
        if sib.exists():
            sib.unlink()


def aggregate_stats(reports: list[ReportSummary]) -> dict:
    total_sources = sum(r.sources_count for r in reports)
    last_run = ""
    if reports:
        last_run = reports[0].generated_at
    return {
        "total_reports": len(reports),
        "total_sources": total_sources,
        "last_run": last_run,
    }


def parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None
