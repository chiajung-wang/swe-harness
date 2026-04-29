# CONTEXT.md

Canonical terms and resolved design decisions for `swe-harness`.

## Glossary

**Run** — a single end-to-end execution of the harness against one GitHub issue. Identified by `run_id` (`<timestamp>-<issue-slug>`).

**Round** — one Generator → Evaluator cycle within a run. Max 3 rounds per run.

**Fix contract** — structured artifact (`fix_contract.json`) produced by the Reproducer. Defines what the Generator must satisfy.

**Verdict** — structured artifact (`verdict.json`) produced by the Evaluator. Pass or fail with reasons.

**Sprint-contract proposal** — structured JSON the Generator submits before coding. Evaluator must approve before any file edits.

**Hack** — a Generator output that makes the target test pass without fixing the underlying bug. See ADR 0002 for the enumerated list.

**Stall** — a run terminated by the orchestrator due to detected non-progress. Not retried automatically.

**Config** — one of four ablation configurations: `solo`, `two_agent`, `three_agent`, `full`.

**Eval set** — one of three fixed bug collections: `dev` (n=10), `custom` (n=15), `swebench` (n=30).

## Resolved design decisions

| Decision | Choice | ADR |
|---|---|---|
| Agent communication | Disk-based JSON artifacts | 0001 |
| Run artifact layout | `runs/<timestamp>-<issue-slug>/` | — |
| Retry feedback | Cumulative rejection reasons + current diff | — |
| Sprint-contract proposal format | `{files_to_modify, approach, risks}` JSON | — |
| Evaluator hack checklist | 6 diff-based + 1 runtime check | 0002 |
| Docker lifecycle | Orchestrator manages; agents outside; one container per run | 0003 |
| MCP backend split | jedi for definitions/usages; tree-sitter for test lookup; git for commits | 0004 |
| MCP access | Reproducer + Generator only; Evaluator excluded | 0004 |
| Prompt caching | Always cache system prompts + all repo files | 0005 |
| Budget enforcement | Orchestrator enforces; agents unaware | — |
| Stall detection | 4 heuristics: 60s idle, identical tool×3, same file patch×5, Reproducer >20 calls | — |
| Trace format | NDJSON, one entry per event | — |
| SQLite schema | Single `runs` table; per-call detail stays in trace files | — |

## Artifact schemas (canonical)

### `fix_contract.json`
```json
{
  "issue_url": "",
  "repo_commit": "",
  "failing_test": "",
  "repro_command": "",
  "expected_behavior": "",
  "likely_affected_files": [],
  "error_output": "",
  "reproducer_confidence": "high|medium|low"
}
```

### Sprint-contract proposal
```json
{
  "files_to_modify": [],
  "approach": "",
  "risks": ""
}
```

### `verdict.json`
```json
{
  "run_id": "",
  "round": 1,
  "verdict": "pass|fail",
  "hacks_detected": [],
  "regressions": [],
  "feedback": "",
  "suite_passed": true,
  "suite_total": 0,
  "suite_failed": 0
}
```

### Trace entry (NDJSON)
```json
{"ts": "", "run_id": "", "agent": "", "event": "tool_call|model_call|artifact_written", "model": "", "tool": "", "input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cost_usd": 0.0, "duration_ms": 0}
```
