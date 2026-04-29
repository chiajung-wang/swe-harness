# ADR 0002: Evaluator hack-detection checklist

**Status:** Accepted  
**Date:** 2026-04-29

## Decision

The Evaluator checks for 7 classes of invalid fixes before accepting a Generator patch.

## Checklist

Diff-based (checked before running the test suite):
1. Pre-existing test file modified
2. Pre-existing test deleted
3. `pytest.skip` / `unittest.skip` added to a test
4. Expected value hardcoded to match test input rather than logic fixed
5. Exception caught/swallowed at the call site
6. `if` guard added that special-cases the test input

Runtime:
7. Full test suite run reveals regressions (tests that passed before now fail)

## Rationale

Items 1–6 are detectable via `git diff` against pre-existing test files — fail fast before spending tokens on a full suite run. Item 7 requires execution. Ordering: diff checks first, suite run only if all diff checks pass.
