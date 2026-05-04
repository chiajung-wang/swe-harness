# ADR 0006: Reproducer uses Sonnet 4.6, not Haiku

**Status:** Accepted
**Date:** 2026-05-04

## Decision

`Reproducer` uses `claude-sonnet-4-6`. Generator uses `claude-haiku-4-5-20251001`.

## Rationale

Reproducer's task is harder than Generator's. Generator receives a pre-filled `fix_contract.json` with exact failing test path, error output, and likely affected files — it just needs to patch code. Reproducer starts from a raw GitHub issue URL and must:
- Understand the bug from issue prose
- Explore an unfamiliar repo
- Write a correct failing test from scratch
- Confirm the test targets the actual bug

A bad `fix_contract.json` wastes the entire Generator budget on the wrong problem. Paying more per token at the Reproducer stage is cheaper than burning Generator runs on a weak contract.

Opus 4.7 reserved for hard cases only (per project budget policy).

## Trade-offs

Sonnet 4.6 is ~3.75× more expensive per input token than Haiku 4.5. Reproducer's 20-call cap (vs Generator's 50) partially offsets this. Acceptable given the quality-gate role.
