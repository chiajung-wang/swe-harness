from typing import Any

import pytest
from pydantic import ValidationError

from swe_harness.models import FixContract, RunRecord, SprintContract, TraceEntry, Verdict


def make_fix_contract(**overrides: Any) -> FixContract:
    data = {
        "issue_url": "https://github.com/org/repo/issues/1",
        "repo_commit": "abc123",
        "failing_test": "tests/test_foo.py::test_bar",
        "repro_command": "pytest tests/test_foo.py::test_bar",
        "expected_behavior": "should not raise",
        "likely_affected_files": ["src/foo.py"],
        "error_output": "AssertionError",
        "reproducer_confidence": "high",
    }
    data.update(overrides)
    return FixContract(**data)


def test_fix_contract_round_trip() -> None:
    contract = make_fix_contract()
    assert FixContract.model_validate_json(contract.model_dump_json()) == contract


def test_fix_contract_confidence_rejects_invalid() -> None:
    with pytest.raises(ValidationError):
        make_fix_contract(reproducer_confidence="very_high")


def make_verdict(**overrides: Any) -> Verdict:
    data = {
        "run_id": "20240101-000000-repo-1",
        "round": 1,
        "verdict": "pass",
        "hacks_detected": [],
        "regressions": [],
        "feedback": "",
        "suite_passed": True,
        "suite_total": 10,
        "suite_failed": 0,
    }
    data.update(overrides)
    return Verdict(**data)


def test_verdict_round_trip() -> None:
    verdict = make_verdict()
    assert Verdict.model_validate_json(verdict.model_dump_json()) == verdict


def test_verdict_rejects_invalid_verdict_field() -> None:
    with pytest.raises(ValidationError):
        make_verdict(verdict="unknown")


def test_sprint_contract_round_trip() -> None:
    sc = SprintContract(files_to_modify=["src/foo.py"], approach="rewrite loop", risks="none")
    assert SprintContract.model_validate_json(sc.model_dump_json()) == sc


def make_trace_entry(**overrides: Any) -> TraceEntry:
    data: dict[str, Any] = {
        "ts": "2024-01-01T00:00:00Z",
        "run_id": "20240101-000000-repo-1",
        "agent": "generator",
        "event": "tool_call",
        "model": None,
        "tool": "bash",
        "input_tokens": 100,
        "output_tokens": 50,
        "cache_read_tokens": 0,
        "cost_usd": 0.001,
        "duration_ms": 200,
    }
    data.update(overrides)
    return TraceEntry(**data)


def test_trace_entry_round_trip() -> None:
    entry = make_trace_entry()
    assert TraceEntry.model_validate_json(entry.model_dump_json()) == entry


def test_trace_entry_rejects_invalid_event() -> None:
    with pytest.raises(ValidationError):
        make_trace_entry(event="unknown_event")


def test_run_record_round_trip() -> None:
    record = RunRecord(
        run_id="20240101-000000-repo-1",
        issue_url="https://github.com/org/repo/issues/1",
        config="solo",
        verdict=None,
        rounds=1,
        cost_usd=0.05,
        duration_s=42.0,
        ts="2024-01-01T00:00:00Z",
    )
    assert RunRecord.model_validate_json(record.model_dump_json()) == record
