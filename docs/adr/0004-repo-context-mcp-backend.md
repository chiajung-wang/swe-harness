# ADR 0004: repo-context-mcp backend per tool

**Status:** Accepted  
**Date:** 2026-04-29

## Decision

Split backend by tool rather than using one backend for everything:

| Tool | Backend | Reason |
|---|---|---|
| `find_definition` | jedi | Cross-file resolution requires type inference |
| `find_usages` | jedi | Cross-file resolution requires type inference |
| `list_recent_commits` | git log | No AST needed |
| `get_test_for_function` | tree-sitter | Pattern matching only; faster than jedi |

Evaluator has no access to `repo-context-mcp` — it only runs tests and inspects diffs.

## Rationale

tree-sitter alone can't reliably track references across modules. jedi handles cross-file resolution but is slower. Splitting avoids paying jedi's startup cost for operations that don't need it.
