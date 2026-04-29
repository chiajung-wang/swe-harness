# ADR 0005: Prompt caching strategy

**Status:** Accepted  
**Date:** 2026-04-29

## Decision

Always apply `cache_control: ephemeral` to:
1. All system prompts
2. All repo file content loaded into any prompt

Do not track per-file load frequency — cache unconditionally.

## Prompt structure (stable prefix order)

```
[system prompt]          ← cache breakpoint
[repo file context]      ← cache breakpoint  
[task instructions]      ← no cache (changes per turn)
```

## Rationale

Cache write fee (~25% of input token cost) on a single-read file is negligible vs. the complexity of tracking load frequency across multi-turn agent loops. System prompts are always multi-turn. Repo files are frequently re-read by Generator during iteration.

Anthropic requires breakpoints at stable prefix boundaries — system prompt and repo context are stable; task instructions vary per turn.
