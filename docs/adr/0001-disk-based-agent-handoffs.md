# ADR 0001: Disk-based agent handoffs

**Status:** Accepted  
**Date:** 2026-04-29

## Decision

Agents communicate via structured JSON files on disk (`fix_contract.json`, `verdict.json`) rather than in-memory Python objects or a message queue.

## Alternatives considered

- **In-memory objects** — simpler, no I/O, but agents can't be restarted independently after a crash and artifacts aren't inspectable without a debugger.
- **SQLite/message queue** — durable but adds infrastructure and coupling.

## Rationale

- Crash recovery: any agent can be re-run from the last artifact without replaying earlier stages.
- Debuggability: `cat runs/<id>/fix_contract.json` after a failure gives instant triage.
- Natural audit trail: artifacts are part of the structured trace log at no extra cost.
- Latency of file I/O is irrelevant relative to LLM call time.
