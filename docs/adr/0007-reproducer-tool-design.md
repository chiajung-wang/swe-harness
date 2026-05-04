# ADR 0007: Reproducer tool design — write_test and emit_contract

**Status:** Accepted
**Date:** 2026-05-04

## Decision

Reproducer gets two purpose-specific tools in addition to the shared set:

- **`write_test`** — writes files only under `tests/`. Separate from `write_file`, which blocks `tests/` paths.
- **`emit_contract`** — structured completion signal. Model supplies 6 fields; system fills `issue_url` + `repo_commit`. Validated via Pydantic before accepting. Loop exits on success. Excluded from the 20-call cap.

## Rationale

### write_test vs lifting write_file restriction

Generator explicitly blocks `tests/` in `write_file` to prevent test corruption. Simply lifting that restriction for Reproducer would conflate two distinct intents (fix code vs write a reproducer test) in one tool, making the model's behavior harder to control and audit.

A dedicated `write_test` tool signals the model's role clearly, keeps Generator's test-guard invariant intact if tool definitions are ever shared, and makes it impossible for Reproducer to accidentally write to `tests/` via `write_file`.

### emit_contract vs text parsing or file copy

Alternatives considered:
- **Text parsing** — model's final message contains JSON; system parses it. Fragile: any prose around the JSON breaks parsing; no schema enforcement until after the loop.
- **write_file to /repo/fix_contract.json** — writes inside Docker, requires a copy-out step; model could hallucinate `issue_url` or `repo_commit`.
- **emit_contract tool** — Pydantic validation fires before the loop exits; malformed contracts are returned as tool errors and the model can retry. System owns the two ground-truth fields (`issue_url`, `repo_commit`) that the model cannot improve on. Loop termination is unambiguous.

Excluding `emit_contract` from the cap prevents a model that correctly wrote the test in 17 calls from being killed during Pydantic retry on the final step.
