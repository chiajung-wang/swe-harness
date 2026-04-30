from __future__ import annotations

import datetime
from pathlib import Path

from anthropic.types import Usage

from swe_harness.models import TraceEntry


def _now_iso() -> str:
    # UTC throughout — agents may run in different timezones inside Docker
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class Tracer:
    """Append-only NDJSON writer. One JSON line per TraceEntry, no buffering.

    Safe for sequential use across agents: each .log() opens, writes, and
    closes the file independently, so no file handle is held between calls.
    Not safe for concurrent writes from multiple processes simultaneously.
    """

    def __init__(self, run_dir: Path) -> None:
        # Create the run directory if it doesn't exist yet — orchestrator
        # passes the run dir before any agents have written to it.
        run_dir.mkdir(parents=True, exist_ok=True)
        self._path = run_dir / "trace.ndjson"
        # Touch so the file exists even before the first log() call,
        # allowing downstream tools to tail it from the start of a run.
        self._path.touch()

    def log(self, entry: TraceEntry) -> None:
        # Open in append mode on every call rather than holding a file handle,
        # so a crash mid-run doesn't corrupt or lose earlier entries.
        with self._path.open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json())
            f.write("\n")


def entry_from_usage(
    *,
    run_id: str,
    agent: str,
    model: str,
    usage: Usage,
    cost_usd: float,
    duration_ms: int = 0,
) -> TraceEntry:
    """Build a model_call TraceEntry from an Anthropic Usage response object.

    Callers are responsible for computing cost_usd from token counts and
    model pricing — the SDK Usage object does not include cost directly.

    Keyword-only args prevent silent positional mistakes across the many
    string parameters.
    """
    cache_read: int = (
        usage.cache_read_input_tokens if usage.cache_read_input_tokens is not None else 0
    )
    return TraceEntry(
        ts=_now_iso(),
        run_id=run_id,
        agent=agent,
        event="model_call",
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=cache_read,
        cost_usd=cost_usd,
        duration_ms=duration_ms,
    )
