from pathlib import Path

import pytest

from swe_harness.models import TraceEntry
from swe_harness.tracer import Tracer, entry_from_usage


def _entry(**kwargs: object) -> TraceEntry:
    defaults: dict[str, object] = {
        "ts": "2024-01-01T00:00:00+00:00",
        "run_id": "run-1",
        "agent": "reproducer",
        "event": "model_call",
    }
    defaults.update(kwargs)
    return TraceEntry.model_validate(defaults)


def test_creates_file_on_init(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    Tracer(run_dir)
    assert (run_dir / "trace.ndjson").exists()


def test_log_three_entries_round_trip(tmp_path: Path) -> None:
    tracer = Tracer(tmp_path)
    entries = [_entry(run_id=f"run-{i}") for i in range(3)]
    for e in entries:
        tracer.log(e)

    lines = (tmp_path / "trace.ndjson").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    parsed = [TraceEntry.model_validate_json(line) for line in lines]
    assert parsed == entries


def test_append_mode_across_instances(tmp_path: Path) -> None:
    Tracer(tmp_path).log(_entry(run_id="a"))
    Tracer(tmp_path).log(_entry(run_id="b"))

    lines = (tmp_path / "trace.ndjson").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_entry_from_usage_maps_tokens() -> None:
    from anthropic.types import Usage

    usage = Usage(input_tokens=100, output_tokens=50, cache_read_input_tokens=20)
    entry = entry_from_usage(
        run_id="run-1",
        agent="generator",
        model="claude-haiku-4-5",
        usage=usage,
        cost_usd=0.0012,
        duration_ms=800,
    )

    assert entry.input_tokens == 100
    assert entry.output_tokens == 50
    assert entry.cache_read_tokens == 20
    assert entry.cost_usd == pytest.approx(0.0012)
    assert entry.duration_ms == 800
    assert entry.event == "model_call"


def test_entry_from_usage_no_cache() -> None:
    from anthropic.types import Usage

    usage = Usage(input_tokens=10, output_tokens=5)
    entry = entry_from_usage(
        run_id="run-1",
        agent="reproducer",
        model="claude-sonnet-4-6",
        usage=usage,
        cost_usd=0.0,
    )

    assert entry.cache_read_tokens == 0
