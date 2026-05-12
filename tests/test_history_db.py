"""SQLite history DB: insert, list, filter, aggregate, reindex."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def isolated_reports(tmp_path, monkeypatch):
    """Point settings.output_folder to a tmp dir; force history DB into it."""
    from researchhq.config import settings
    monkeypatch.setattr(settings, "output_folder", str(tmp_path))
    yield tmp_path


def _payload(mode: str, query: str, sources: int = 2, conf: float = 0.8) -> dict:
    return {
        "mode": mode,
        "query": query,
        "generated_at": "2026-05-06T12:00:00+00:00",
        "provider_used": "mock",
        "verifier": {
            "overall_confidence": conf,
            "rules": [{"name": "x", "severity": "info", "passed": True, "message": ""}],
            "violations": [],
        },
        "sources": [{"url": f"u{i}", "tier": "news", "score": 8} for i in range(sources)],
        "facts": [],
        "stage_costs": [
            {"stage": "planner", "calls": 1, "input_tokens": 10, "output_tokens": 5,
             "equivalent_paid_cost_usd": 0.001},
        ],
    }


def test_insert_and_list_runs(isolated_reports):
    from researchhq import history as h
    p1 = isolated_reports / "topic__a.json"
    p1.write_text("{}", encoding="utf-8")
    h.index_report_dict(p1, _payload("topic", "alpha"))

    rows = h.list_runs()
    assert len(rows) == 1
    assert rows[0].query == "alpha"
    assert rows[0].mode == "topic"
    assert rows[0].sources_count == 2


def test_filter_by_mode(isolated_reports):
    from researchhq import history as h
    a = isolated_reports / "topic__a.json"; a.write_text("{}")
    b = isolated_reports / "company__b.json"; b.write_text("{}")
    h.index_report_dict(a, _payload("topic", "alpha"))
    h.index_report_dict(b, _payload("company", "beta"))

    assert {r.mode for r in h.list_runs(mode="topic")} == {"topic"}
    assert {r.mode for r in h.list_runs(mode="company")} == {"company"}


def test_text_search(isolated_reports):
    from researchhq import history as h
    a = isolated_reports / "topic__a.json"; a.write_text("{}")
    h.index_report_dict(a, _payload("topic", "Supabase deep dive"))
    rows = h.list_runs(text="supabase")
    assert any("Supabase" in r.query for r in rows)


def test_workspace_filtering(isolated_reports):
    from researchhq import history as h
    a = isolated_reports / "topic__a.json"; a.write_text("{}")
    b = isolated_reports / "topic__b.json"; b.write_text("{}")
    h.index_report_dict(a, _payload("topic", "alpha"), workspace="default")
    h.index_report_dict(b, _payload("topic", "beta"), workspace="acme")

    assert {r.query for r in h.list_runs(workspace="default")} == {"alpha"}
    assert {r.query for r in h.list_runs(workspace="acme")} == {"beta"}
    assert {r.query for r in h.list_runs(workspace="all")} == {"alpha", "beta"}


def test_aggregate_totals(isolated_reports):
    from researchhq import history as h
    a = isolated_reports / "topic__a.json"; a.write_text("{}")
    b = isolated_reports / "topic__b.json"; b.write_text("{}")
    h.index_report_dict(a, _payload("topic", "alpha", sources=3))
    h.index_report_dict(b, _payload("topic", "beta", sources=5))
    agg = h.aggregate(workspace="all")
    assert agg["total_reports"] == 2
    assert agg["total_sources"] == 8


def test_delete_run(isolated_reports):
    from researchhq import history as h
    p = isolated_reports / "topic__a.json"; p.write_text("{}")
    h.index_report_dict(p, _payload("topic", "alpha"))
    assert len(h.list_runs()) == 1
    h.delete_run(p)
    assert len(h.list_runs()) == 0


def test_reindex_from_folder(isolated_reports, tmp_path):
    import json
    from researchhq import history as h

    p = isolated_reports / "topic__a.json"
    p.write_text(json.dumps(_payload("topic", "from_disk")), encoding="utf-8")

    n = h.reindex_from_folder(workspace="default")
    assert n == 1
    rows = h.list_runs()
    assert any(r.query == "from_disk" for r in rows)


def test_corrupt_db_recreates(isolated_reports):
    from researchhq import history as h
    # Write garbage to the DB file, then ensure ensure_db recovers.
    db = isolated_reports / ".researchhq.db"
    db.write_bytes(b"not a sqlite database at all")
    h.ensure_db()  # should rename and recreate
    # after recovery, listing succeeds
    assert isinstance(h.list_runs(), list)
