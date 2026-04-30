from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from swe_harness.models import RunRecord

_DEFAULT_DB = Path("runs") / "harness.db"


def _engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{db_path}", future=True)


def init_db(db_path: Path = _DEFAULT_DB) -> None:
    """Create the runs table if it doesn't exist."""
    with _engine(db_path).begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id      TEXT PRIMARY KEY,
                issue_url   TEXT NOT NULL,
                config      TEXT NOT NULL,
                verdict     TEXT,
                rounds      INTEGER NOT NULL,
                cost_usd    REAL NOT NULL,
                duration_s  REAL NOT NULL,
                ts          TEXT NOT NULL
            )
        """))


def upsert_run(record: RunRecord, db_path: Path = _DEFAULT_DB) -> None:
    """Insert or replace a RunRecord row keyed by run_id."""
    with _engine(db_path).begin() as conn:
        conn.execute(
            text("""
                INSERT OR REPLACE INTO runs
                    (run_id, issue_url, config, verdict, rounds, cost_usd, duration_s, ts)
                VALUES
                    (:run_id, :issue_url, :config, :verdict, :rounds, :cost_usd, :duration_s, :ts)
            """),
            {
                "run_id": record.run_id,
                "issue_url": record.issue_url,
                "config": record.config,
                "verdict": record.verdict,
                "rounds": record.rounds,
                "cost_usd": record.cost_usd,
                "duration_s": record.duration_s,
                "ts": record.ts,
            },
        )
