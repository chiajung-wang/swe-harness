## What to build

`src/swe_harness/agents/reproducer.py` — `Reproducer(issue_url, repo_commit, issue_body, run_dir, docker, tracer, budget)`.

Agentic loop that:
1. Explores the target repo via `docker.exec()`
2. Writes a failing test to the repo via `write_test` tool (tests/ only)
3. Confirms the test fails via `run_command("pytest ...")`
4. Calls `emit_contract` tool to finalize and write `fix_contract.json` to `run_dir`

**Model:** `claude-sonnet-4-6`

**Tool set:**
- `read_file` — reads files from `/repo/` (same as Generator)
- `write_file` — writes files to `/repo/`; tests/ paths blocked
- `write_test` — writes files to `/repo/tests/` only; separate tool enforces intent
- `run_command` — runs shell commands inside `/repo/`
- `emit_contract` — completion signal; takes 6 fields (see below); system fills `issue_url` + `repo_commit`; validated via Pydantic before accepting; loop exits on success

**`emit_contract` input schema (model supplies):**
- `failing_test: str` — pytest node ID, e.g. `tests/path/test_foo.py::test_bar`
- `repro_command: str` — shell command that exits non-zero on the bug
- `expected_behavior: str`
- `likely_affected_files: list[str]`
- `error_output: str`
- `reproducer_confidence: "high" | "medium" | "low"` — model self-reports; system overrides to `"low"` if stall cap hit or test never confirmed failing

**Issue content:** Orchestrator pre-fetches GitHub issue body before instantiating Reproducer; injected into the cached initial message. Not a tool call.

**`repo_commit`:** Orchestrator runs `docker.exec("git rev-parse HEAD")` before instantiating Reproducer; injected into initial message. System fills this field in the contract — model never supplies it.

**Stall cap:** 20 tool calls (excluding `emit_contract`).
- At call 17: inject forced message — "You are near your tool call limit. Call `emit_contract` now with your best current understanding."
- At call 20 without `emit_contract`: hard-terminate, system writes `fix_contract.json` with whatever partial state exists and `reproducer_confidence="low"`.

**Confidence override:** System sets `confidence="low"` if stall cap hit OR if test was never confirmed failing (no successful pytest run showing non-zero exit on the failing test).

## Acceptance criteria

- [x] `Reproducer` accepts `(issue_url, repo_commit, issue_body, run_dir, docker, tracer, budget)`
- [x] Tools: `read_file`, `write_file` (tests/ blocked), `write_test` (tests/ only), `run_command`, `emit_contract`
- [x] `emit_contract` excluded from 20-call cap; triggers loop exit on Pydantic-valid input
- [x] System fills `issue_url` + `repo_commit` in emitted contract; model supplies other 6 fields
- [x] Forced inject at call 17; hard-terminate at call 20 with `confidence="low"` contract
- [x] System overrides `confidence="low"` when stall cap hit or test never confirmed failing
- [x] All API calls go through `_call()` → logged to tracer, charged to budget
- [x] `pytest` passes (unit tests with mocked docker/tracer/budget)

## Status

**Done.** PR #15. `src/swe_harness/agents/reproducer.py`, `tests/test_reproducer_agent.py` (11 tests).
