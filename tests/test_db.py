"""Unit tests for db.py — uses a temp SQLite file, no Docker or Anthropic calls."""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

from swe_harness.db import init_db, upsert_run
from swe_harness.models import RunRecord


def _record(**overrides: object) -> RunRecord:
    base: dict[str, object] = {
        "run_id": "20240101T000000-github-com-owner-repo-issues-1",
        "issue_url": "https://github.com/owner/repo/issues/1",
        "config": "solo",
        "verdict": "pass",
        "rounds": 1,
        "cost_usd": 0.0042,
        "duration_s": 12.5,
        "ts": "2024-01-01T00:00:00+00:00",
    }
    base.update(overrides)
    return RunRecord(**base)


def test_init_db_creates_table(tmp_path: Path) -> None:
    db = tmp_path / "harness.db"
    init_db(db)
    engine = create_engine(f"sqlite:///{db}", future=True)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='runs'")).fetchall()
    assert len(rows) == 1


def test_init_db_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "harness.db"
    init_db(db)
    init_db(db)  # second call must not raise


def test_upsert_run_inserts(tmp_path: Path) -> None:
    db = tmp_path / "harness.db"
    init_db(db)
    rec = _record()
    upsert_run(rec, db)

    engine = create_engine(f"sqlite:///{db}", future=True)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM runs WHERE run_id = :id"), {"id": rec.run_id}).fetchone()
    assert row is not None
    assert row.verdict == "pass"
    assert abs(row.cost_usd - 0.0042) < 1e-9


def test_upsert_run_updates(tmp_path: Path) -> None:
    db = tmp_path / "harness.db"
    init_db(db)
    rec = _record(verdict="fail")
    upsert_run(rec, db)

    updated = _record(verdict="pass", cost_usd=0.01)
    upsert_run(updated, db)

    engine = create_engine(f"sqlite:///{db}", future=True)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT verdict, cost_usd FROM runs WHERE run_id = :id"), {"id": rec.run_id}).fetchall()
    assert len(rows) == 1
    assert rows[0].verdict == "pass"


def test_upsert_run_none_verdict(tmp_path: Path) -> None:
    db = tmp_path / "harness.db"
    init_db(db)
    rec = _record(verdict=None)
    upsert_run(rec, db)

    engine = create_engine(f"sqlite:///{db}", future=True)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT verdict FROM runs WHERE run_id = :id"), {"id": rec.run_id}).fetchone()
    assert row is not None
    assert row.verdict is None
