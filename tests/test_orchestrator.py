"""Unit tests for orchestrator.py — Docker, Generator, and Anthropic calls are mocked."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from swe_harness.budget import BudgetExceeded
from swe_harness.models import FixContract, RunRecord
from swe_harness import orchestrator


def _fix_contract() -> FixContract:
    return FixContract(
        issue_url="https://github.com/owner/repo/issues/1",
        repo_commit="abc123",
        failing_test="tests/test_bug.py::test_it",
        repro_command="pytest tests/test_bug.py::test_it",
        expected_behavior="Should return 42",
        likely_affected_files=["src/module.py"],
        error_output="AssertionError",
        reproducer_confidence="high",
    )


@pytest.fixture()
def mock_docker() -> Iterator[MagicMock]:
    with patch("swe_harness.orchestrator.DockerManager") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


@pytest.fixture()
def mock_generator() -> Iterator[MagicMock]:
    with patch("swe_harness.orchestrator.Generator") as cls:
        instance = MagicMock()
        cls.return_value = instance
        yield instance


def test_run_happy_path(tmp_path: Path, mock_docker: MagicMock, mock_generator: MagicMock) -> None:
    mock_generator.run.return_value = None  # success, no exception

    record = orchestrator.run(
        issue_url="https://github.com/owner/repo/issues/1",
        fix_contract=_fix_contract(),
        config="solo",
        runs_dir=tmp_path,
    )

    assert isinstance(record, RunRecord)
    assert record.verdict == "pass"
    assert record.config == "solo"
    assert record.rounds == 1
    mock_docker.start.assert_called_once_with("https://github.com/owner/repo", "abc123")
    mock_docker.stop.assert_called_once()


def test_run_generator_stall_verdict_fail(
    tmp_path: Path, mock_docker: MagicMock, mock_generator: MagicMock
) -> None:
    from swe_harness.agents.generator import StallDetected
    mock_generator.run.side_effect = StallDetected("no progress")

    record = orchestrator.run(
        issue_url="https://github.com/owner/repo/issues/1",
        fix_contract=_fix_contract(),
        runs_dir=tmp_path,
    )

    assert record.verdict == "fail"
    mock_docker.stop.assert_called_once()


def test_run_budget_exceeded_verdict_none(
    tmp_path: Path, mock_docker: MagicMock, mock_generator: MagicMock
) -> None:
    mock_generator.run.side_effect = BudgetExceeded(spent=201.0, limit=200.0)

    record = orchestrator.run(
        issue_url="https://github.com/owner/repo/issues/1",
        fix_contract=_fix_contract(),
        runs_dir=tmp_path,
    )

    assert record.verdict is None
    mock_docker.stop.assert_called_once()


def test_run_docker_always_stopped_on_exception(
    tmp_path: Path, mock_docker: MagicMock, mock_generator: MagicMock
) -> None:
    mock_docker.start.side_effect = RuntimeError("daemon unavailable")

    with pytest.raises(RuntimeError, match="daemon unavailable"):
        orchestrator.run(
            issue_url="https://github.com/owner/repo/issues/1",
            fix_contract=_fix_contract(),
            runs_dir=tmp_path,
        )

    mock_docker.stop.assert_called_once()


def test_run_writes_sqlite_row(
    tmp_path: Path, mock_docker: MagicMock, mock_generator: MagicMock
) -> None:
    from sqlalchemy import create_engine, text

    mock_generator.run.return_value = None

    orchestrator.run(
        issue_url="https://github.com/owner/repo/issues/1",
        fix_contract=_fix_contract(),
        runs_dir=tmp_path,
    )

    db_path = tmp_path / "harness.db"
    assert db_path.exists()
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT verdict FROM runs")).fetchall()
    assert len(rows) == 1
    assert rows[0].verdict == "pass"


def test_run_trace_file_created(
    tmp_path: Path, mock_docker: MagicMock, mock_generator: MagicMock
) -> None:
    mock_generator.run.return_value = None

    orchestrator.run(
        issue_url="https://github.com/owner/repo/issues/1",
        fix_contract=_fix_contract(),
        runs_dir=tmp_path,
    )

    trace_files = list(tmp_path.glob("*/trace.ndjson"))
    assert len(trace_files) == 1


def test_repo_url_from_issue_invalid() -> None:
    with pytest.raises(ValueError, match="Cannot derive repo URL"):
        orchestrator._repo_url_from_issue("https://example.com/not-a-github-issue")
