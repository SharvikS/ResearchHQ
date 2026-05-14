"""SQLite persistence layer for the ResearchHQ API.

Stores query state, results, pipeline status, and execution logs so the API
can serve status polls and history even after the in-memory pipeline state
has been garbage collected.

Uses the stdlib `sqlite3` module (no extra deps). All writes are wrapped in
a context manager so we never leave the DB in a partial-write state.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator, Optional

logger = logging.getLogger(__name__)

_DB_PATH = Path.home() / ".researchhq" / "api_queries.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_db_path() -> Path:
    return _DB_PATH


@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    con = sqlite3.connect(str(_DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db(db_path: Optional[Path] = None) -> None:
    """Create tables if they don't exist. Safe to call multiple times."""
    global _DB_PATH
    if db_path:
        _DB_PATH = db_path
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with _conn() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS queries (
                id           TEXT PRIMARY KEY,
                raw_query    TEXT NOT NULL,
                mode         TEXT DEFAULT 'general',
                pipeline_mode TEXT DEFAULT 'balanced',
                format       TEXT DEFAULT 'markdown',
                status       TEXT DEFAULT 'queued',
                intent_type  TEXT,
                complexity   INTEGER,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL,
                completed_at TEXT,
                error        TEXT
            );

            CREATE TABLE IF NOT EXISTS pipeline_stages (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id     TEXT NOT NULL REFERENCES queries(id),
                slot_name    TEXT NOT NULL,
                display_name TEXT,
                provider     TEXT,
                status       TEXT DEFAULT 'pending',
                latency_ms   INTEGER,
                error        TEXT,
                updated_at   TEXT
            );

            CREATE TABLE IF NOT EXISTS query_results (
                query_id           TEXT PRIMARY KEY REFERENCES queries(id),
                executive_summary  TEXT,
                detailed_answer    TEXT,
                key_findings       TEXT,
                conflicting_views  TEXT,
                limitations        TEXT,
                confidence_score   REAL,
                confidence_label   TEXT,
                confidence_detail  TEXT,
                sources            TEXT,
                agent_outputs      TEXT,
                execution_metadata TEXT,
                created_at         TEXT
            );

            CREATE TABLE IF NOT EXISTS query_logs (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                query_id   TEXT NOT NULL REFERENCES queries(id),
                level      TEXT DEFAULT 'info',
                stage      TEXT DEFAULT '',
                message    TEXT NOT NULL,
                data       TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_logs_query ON query_logs(query_id);
            CREATE INDEX IF NOT EXISTS idx_stages_query ON pipeline_stages(query_id);
        """)
    logger.debug("API database initialized at %s", _DB_PATH)


# ── Query CRUD ─────────────────────────────────────────────────────────────────

def create_query(
    query_id: str,
    raw_query: str,
    mode: str,
    pipeline_mode: str,
    fmt: str,
) -> None:
    now = _now()
    with _conn() as con:
        con.execute(
            """INSERT INTO queries
               (id, raw_query, mode, pipeline_mode, format, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'queued', ?, ?)""",
            (query_id, raw_query, mode, pipeline_mode, fmt, now, now),
        )


def update_query_status(
    query_id: str,
    status: str,
    error: Optional[str] = None,
    intent_type: Optional[str] = None,
    complexity: Optional[int] = None,
) -> None:
    now = _now()
    completed = now if status in ("complete", "failed", "partial") else None
    with _conn() as con:
        con.execute(
            """UPDATE queries SET status=?, updated_at=?, completed_at=?,
               error=?, intent_type=COALESCE(?, intent_type),
               complexity=COALESCE(?, complexity)
               WHERE id=?""",
            (status, now, completed, error, intent_type, complexity, query_id),
        )


def get_query(query_id: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM queries WHERE id=?", (query_id,)
        ).fetchone()
    return dict(row) if row else None


# ── Pipeline stage tracking ────────────────────────────────────────────────────

def upsert_pipeline_stage(
    query_id: str,
    slot_name: str,
    display_name: str,
    provider: str,
    status: str,
    latency_ms: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    now = _now()
    with _conn() as con:
        existing = con.execute(
            "SELECT id FROM pipeline_stages WHERE query_id=? AND slot_name=?",
            (query_id, slot_name),
        ).fetchone()
        if existing:
            con.execute(
                """UPDATE pipeline_stages
                   SET status=?, latency_ms=COALESCE(?, latency_ms),
                       error=COALESCE(?, error), updated_at=?
                   WHERE query_id=? AND slot_name=?""",
                (status, latency_ms, error, now, query_id, slot_name),
            )
        else:
            con.execute(
                """INSERT INTO pipeline_stages
                   (query_id, slot_name, display_name, provider, status, latency_ms, error, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (query_id, slot_name, display_name, provider, status, latency_ms, error, now),
            )


def get_pipeline_stages(query_id: str) -> list[dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM pipeline_stages WHERE query_id=? ORDER BY id",
            (query_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Result storage ─────────────────────────────────────────────────────────────

def save_result(query_id: str, result_data: dict) -> None:
    now = _now()
    with _conn() as con:
        con.execute(
            """INSERT OR REPLACE INTO query_results
               (query_id, executive_summary, detailed_answer, key_findings,
                conflicting_views, limitations, confidence_score, confidence_label,
                confidence_detail, sources, agent_outputs, execution_metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                query_id,
                result_data.get("executive_summary", ""),
                result_data.get("detailed_answer", ""),
                json.dumps(result_data.get("key_findings", [])),
                json.dumps(result_data.get("conflicting_viewpoints", [])),
                json.dumps(result_data.get("limitations", [])),
                result_data.get("confidence_score", 0.0),
                result_data.get("confidence_label", "low"),
                json.dumps(result_data.get("confidence_breakdown", {})),
                json.dumps(result_data.get("sources", [])),
                json.dumps(result_data.get("agent_outputs", {})),
                json.dumps(result_data.get("execution_metadata", {})),
                now,
            ),
        )


def get_result(query_id: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM query_results WHERE query_id=?", (query_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    for field in ("key_findings", "conflicting_views", "limitations",
                  "confidence_detail", "sources", "agent_outputs", "execution_metadata"):
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


# ── Log storage ────────────────────────────────────────────────────────────────

def append_log(
    query_id: str,
    level: str,
    stage: str,
    message: str,
    data: Optional[dict] = None,
) -> None:
    with _conn() as con:
        con.execute(
            """INSERT INTO query_logs (query_id, level, stage, message, data, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (query_id, level, stage, message, json.dumps(data) if data else None, _now()),
        )


def get_logs(
    query_id: str,
    level: Optional[str] = None,
    stage: Optional[str] = None,
    limit: int = 200,
) -> list[dict]:
    clauses = ["query_id = ?"]
    params: list[Any] = [query_id]
    if level:
        clauses.append("level = ?")
        params.append(level)
    if stage:
        clauses.append("stage = ?")
        params.append(stage)
    params.append(limit)

    with _conn() as con:
        rows = con.execute(
            f"SELECT * FROM query_logs WHERE {' AND '.join(clauses)} ORDER BY id LIMIT ?",
            params,
        ).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        if d.get("data"):
            try:
                d["data"] = json.loads(d["data"])
            except (json.JSONDecodeError, TypeError):
                pass
        result.append(d)
    return result
