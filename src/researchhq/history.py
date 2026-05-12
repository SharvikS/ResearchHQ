"""SQLite-backed run history index.

Schema is intentionally tiny: one row per saved report with the metadata we
need for filtering. The full report is still the JSON file on disk; we only
index it. If the DB file goes missing or gets corrupted we rebuild from disk.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from researchhq.config import settings

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    json_path TEXT NOT NULL UNIQUE,
    mode TEXT NOT NULL,
    query TEXT NOT NULL,
    workspace TEXT NOT NULL DEFAULT 'default',
    provider TEXT,
    model TEXT,
    confidence REAL,
    sources_count INTEGER NOT NULL DEFAULT 0,
    facts_count INTEGER NOT NULL DEFAULT 0,
    rules_failed INTEGER NOT NULL DEFAULT 0,
    equivalent_cost_usd REAL NOT NULL DEFAULT 0.0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    elapsed_s REAL NOT NULL DEFAULT 0.0,
    generated_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_runs_workspace ON runs(workspace);
CREATE INDEX IF NOT EXISTS idx_runs_mode ON runs(mode);
CREATE INDEX IF NOT EXISTS idx_runs_generated_at ON runs(generated_at);
"""


@dataclass
class RunRow:
    id: int
    json_path: str
    mode: str
    query: str
    workspace: str
    provider: str | None
    model: str | None
    confidence: float | None
    sources_count: int
    facts_count: int
    rules_failed: int
    equivalent_cost_usd: float
    input_tokens: int
    output_tokens: int
    elapsed_s: float
    generated_at: str


def db_path() -> Path:
    return Path(settings.output_folder) / ".researchhq.db"


def _legacy_db_path() -> Path:
    return Path(settings.output_folder) / ".researchiq.db"


def _connect() -> sqlite3.Connection:
    p = db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    legacy = _legacy_db_path()
    if legacy.exists() and not p.exists():
        legacy.rename(p)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_db() -> None:
    """Create schema if missing. Safe to call repeatedly."""
    try:
        with closing(_connect()) as conn:
            conn.executescript(_SCHEMA)
            conn.commit()
    except sqlite3.DatabaseError as e:
        # Corrupted DB: rename and recreate so the app keeps working.
        broken = db_path().with_suffix(".db.broken")
        try:
            db_path().rename(broken)
            logger.warning("History DB was corrupt; moved to %s", broken)
        except Exception:  # noqa: BLE001
            pass
        with closing(_connect()) as conn:
            conn.executescript(_SCHEMA)
            conn.commit()


def index_report_dict(json_path: str | Path, report: dict, workspace: str = "default") -> None:
    """Insert/replace a row from a freshly-saved or freshly-loaded report dict."""
    ensure_db()
    json_path = str(Path(json_path).resolve())
    verifier = report.get("verifier") or {}
    rules = verifier.get("rules") or []
    rules_failed = sum(1 for r in rules if not r.get("passed", True))
    stage_costs = report.get("stage_costs") or []
    in_tok = sum(int(s.get("input_tokens", 0)) for s in stage_costs)
    out_tok = sum(int(s.get("output_tokens", 0)) for s in stage_costs)
    cost = sum(float(s.get("equivalent_paid_cost_usd", 0.0)) for s in stage_costs)
    row = (
        json_path,
        report.get("mode", "?"),
        report.get("query", ""),
        workspace,
        report.get("provider_used") or None,
        None,
        verifier.get("overall_confidence"),
        len(report.get("sources") or []),
        len(report.get("facts") or []),
        rules_failed,
        round(cost, 4),
        in_tok,
        out_tok,
        0.0,  # elapsed_s not in saved JSON; left at 0
        report.get("generated_at", ""),
    )
    with closing(_connect()) as conn:
        conn.execute(
            """
            INSERT INTO runs (
                json_path, mode, query, workspace, provider, model, confidence,
                sources_count, facts_count, rules_failed, equivalent_cost_usd,
                input_tokens, output_tokens, elapsed_s, generated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(json_path) DO UPDATE SET
                mode=excluded.mode,
                query=excluded.query,
                workspace=excluded.workspace,
                provider=excluded.provider,
                model=excluded.model,
                confidence=excluded.confidence,
                sources_count=excluded.sources_count,
                facts_count=excluded.facts_count,
                rules_failed=excluded.rules_failed,
                equivalent_cost_usd=excluded.equivalent_cost_usd,
                input_tokens=excluded.input_tokens,
                output_tokens=excluded.output_tokens,
                generated_at=excluded.generated_at
            """,
            row,
        )
        conn.commit()


def list_runs(
    workspace: str | None = None,
    mode: str | None = None,
    text: str | None = None,
    limit: int = 200,
) -> list[RunRow]:
    ensure_db()
    where: list[str] = []
    args: list[object] = []
    if workspace and workspace != "all":
        where.append("workspace = ?"); args.append(workspace)
    if mode:
        where.append("mode = ?"); args.append(mode)
    if text:
        where.append("(query LIKE ? OR mode LIKE ? OR provider LIKE ?)")
        like = f"%{text}%"; args.extend([like, like, like])
    sql = "SELECT * FROM runs"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY generated_at DESC LIMIT ?"; args.append(limit)
    with closing(_connect()) as conn:
        rows = conn.execute(sql, args).fetchall()
    return [_to_run_row(r) for r in rows]


def get_run(json_path: str | Path) -> RunRow | None:
    ensure_db()
    p = str(Path(json_path).resolve())
    with closing(_connect()) as conn:
        row = conn.execute("SELECT * FROM runs WHERE json_path = ?", (p,)).fetchone()
    return _to_run_row(row) if row else None


def delete_run(json_path: str | Path) -> None:
    ensure_db()
    p = str(Path(json_path).resolve())
    with closing(_connect()) as conn:
        conn.execute("DELETE FROM runs WHERE json_path = ?", (p,))
        conn.commit()


def list_workspaces() -> list[str]:
    ensure_db()
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT DISTINCT workspace FROM runs ORDER BY workspace ASC"
        ).fetchall()
    out = [r["workspace"] for r in rows]
    if "default" not in out:
        out.insert(0, "default")
    return out


def aggregate(workspace: str | None = None) -> dict:
    """Total counts/cost for the dashboard."""
    ensure_db()
    where = ""
    args: list[object] = []
    if workspace and workspace != "all":
        where = " WHERE workspace = ?"
        args.append(workspace)
    with closing(_connect()) as conn:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS n,
                   COALESCE(SUM(sources_count), 0) AS sources,
                   COALESCE(SUM(equivalent_cost_usd), 0.0) AS cost,
                   COALESCE(SUM(input_tokens), 0) AS in_tok,
                   COALESCE(SUM(output_tokens), 0) AS out_tok
            FROM runs{where}
            """,
            args,
        ).fetchone()
        last = conn.execute(
            f"SELECT equivalent_cost_usd, generated_at FROM runs{where} "
            "ORDER BY generated_at DESC LIMIT 1",
            args,
        ).fetchone()
    return {
        "total_reports": int(row["n"] or 0),
        "total_sources": int(row["sources"] or 0),
        "total_cost": float(row["cost"] or 0.0),
        "input_tokens": int(row["in_tok"] or 0),
        "output_tokens": int(row["out_tok"] or 0),
        "last_run_cost": float(last["equivalent_cost_usd"]) if last else 0.0,
        "last_run_at": last["generated_at"] if last else "",
    }


def reindex_from_folder(folder: str | Path | None = None, workspace: str = "default") -> int:
    """Scan reports folder for JSON files and (re)index them. Returns count."""
    folder = Path(folder or settings.output_folder)
    if not folder.exists():
        return 0
    n = 0
    for p in folder.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if "mode" not in data or "query" not in data:
            continue  # not one of ours
        try:
            index_report_dict(p, data, workspace=workspace)
            n += 1
        except Exception:  # noqa: BLE001
            logger.exception("reindex failed for %s", p)
    return n


def _to_run_row(r: sqlite3.Row | Iterable) -> RunRow:
    return RunRow(
        id=int(r["id"]),
        json_path=str(r["json_path"]),
        mode=str(r["mode"]),
        query=str(r["query"]),
        workspace=str(r["workspace"]),
        provider=r["provider"],
        model=r["model"],
        confidence=r["confidence"],
        sources_count=int(r["sources_count"] or 0),
        facts_count=int(r["facts_count"] or 0),
        rules_failed=int(r["rules_failed"] or 0),
        equivalent_cost_usd=float(r["equivalent_cost_usd"] or 0.0),
        input_tokens=int(r["input_tokens"] or 0),
        output_tokens=int(r["output_tokens"] or 0),
        elapsed_s=float(r["elapsed_s"] or 0.0),
        generated_at=str(r["generated_at"] or ""),
    )
