# swe-harness Implementation Plan

## Context

Pre-implementation. Scaffold exists (pyproject.toml, deps, hooks, src/swe_harness/__init__.py).
PRD defines 6-week milestones with hard exit criteria. 15 architectural decisions resolved (CONTEXT.md + 5 ADRs).
Goal: milestone-gated build order that lets each week's code run end-to-end before the next begins.

---

## Module layout (target)

```
src/swe_harness/
├── cli.py                  # Click: run / eval / traces
├── models.py               # Pydantic: FixContract, Verdict, SprintContract, TraceEntry, RunRecord
├── tracer.py               # NDJSON writer; wraps Anthropic callbacks
├── db.py                   # SQLAlchemy: single `runs` table
├── docker_manager.py       # spin-up / exec / teardown; reuse across rounds
├── budget.py               # spend accumulator + hard-kill at $50/$100/$150
├── orchestrator.py         # run lifecycle; stall detection; round loop
└── agents/
    ├── base.py             # AnthropicAgent: client init, prompt-cache helper, tool-call counter
    ├── reproducer.py       # Reproducer → fix_contract.json
    ├── generator.py        # Generator → patch; sprint-contract proposal
    └── evaluator.py        # Evaluator → verdict.json; hack checklist

src/repo_context_mcp/
├── server.py               # MCP server entry (stdio)
├── jedi_backend.py         # find_definition, find_usages
├── tree_sitter_backend.py  # get_test_for_function
└── git_backend.py          # list_recent_commits

eval/datasets/
├── dev/                    # 10 pinned SWE-bench bugs (JSON manifests)
├── custom/                 # 15 custom OSS bugs
└── swebench/               # 30 SWE-bench Verified instance IDs
```

---

## Week 1 — Solo baseline + traces
**Exit criteria:** End-to-end `swe-harness run <issue-url>` on a real issue, full NDJSON trace written.

### Tasks (build order — each unblocks the next)

1. **`models.py`** — Pydantic models: `FixContract`, `Verdict`, `SprintContract`, `TraceEntry`, `RunRecord`. Source of truth for all JSON artifacts (schemas from CONTEXT.md).

2. **`tracer.py`** — `Tracer(run_dir)`: opens `trace.ndjson`, exposes `log(entry: TraceEntry)`. Wrap Anthropic `usage` objects into token/cost fields. No side effects beyond append-to-file.

3. **`docker_manager.py`** — `DockerManager`: `start(repo_url, commit) → container_id`, `exec(cmd) → stdout/stderr`, `stop()`. Mounts repo at `/repo`. Reuses container across rounds (stop only called by orchestrator at run end or on timeout).

4. **`budget.py`** — `Budget(limit_usd)`: `.charge(cost)` accumulates spend; raises `BudgetExceeded` at $50/$100/$150 (warns) and hard-raises at limit. Orchestrator holds the instance.

5. **`agents/base.py`** — `AnthropicAgent`: initializes `anthropic.Anthropic()`, holds `Tracer` + `Budget` refs, provides `_build_cache_block(content)` (wraps text in `{"type":"text","text":...,"cache_control":{"type":"ephemeral"}}`) and `_call(system, messages, tools)` that logs to tracer and charges budget.

6. **`agents/generator.py`** — `Generator(fix_contract, run_dir, docker, tracer, budget)`: reads `fix_contract.json`, runs agentic loop (tool-call cap: 50, wall-clock: 15 min), writes patch via `docker exec`. No sprint-contract yet (week 3). Stall detection: identical tool ×3, same file patch ×5, 60s idle.

7. **`orchestrator.py`** — `run(issue_url, config="solo")`: creates `runs/<ts>-<slug>/`, starts Docker, runs Generator, writes `RunRecord` to SQLite, tears down container.

8. **`db.py`** — `init_db()`, `upsert_run(record: RunRecord)`. Single `runs` table: `run_id, issue_url, config, verdict, rounds, cost_usd, duration_s, ts`.

9. **`cli.py`** — `swe-harness run <issue-url> [--config solo]`. Rich progress output. Calls `orchestrator.run()`.

---

## Week 2 — Reproducer + two-agent + eval CLI
**Exit criteria:** Reproducer + Generator beats solo on 10-bug dev set; `swe-harness eval dev` works.

### Tasks

1. **`agents/reproducer.py`** — `Reproducer(issue_url, run_dir, docker, tracer, budget)`: explores repo, writes failing test, confirms it fails, emits `fix_contract.json`. Stall cap: 20 tool calls (CONTEXT.md). Confidence field: `high|medium|low`.

2. **Orchestrator: two-agent config** — `config="two_agent"` runs Reproducer → Generator in sequence. Generator reads `fix_contract.json` from run dir.

3. **`eval/datasets/dev/`** — 10 JSON manifests: `{instance_id, repo_url, commit, issue_url, gold_test}`. Pin commits now so results are reproducible.

4. **`cli.py` eval command** — `swe-harness eval dev` iterates dataset, calls `orchestrator.run()` per instance, aggregates pass@1 into `eval/results/dev-<ts>.json`.

5. **`db.py`** — add `eval_set`, `instance_id` columns to runs table.

---

## Week 3 — Evaluator + sprint-contract + full ablation
**Exit criteria:** Full ablation table (solo / two-agent / three-agent / full) on dev set.

### Tasks

1. **`agents/evaluator.py`** — `Evaluator(run_dir, docker, tracer, budget)`:
   - Hack checklist (ADR 0002): 6 diff checks (git diff vs pre-existing tests) + full suite run.
   - Emits `verdict.json` (schema from CONTEXT.md).
   - On fail: structured `feedback` field consumed by Generator in next round.

2. **Orchestrator: retry loop** — max 3 rounds. Each round: Generator → Evaluator. Feedback passed as cumulative rejection reasons + current diff. Container reused (not re-cloned).

3. **Sprint-contract negotiation** — before Generator codes: Generator emits `sprint_contract.json` (`{files_to_modify, approach, risks}`), Evaluator approves or rejects (max 2 negotiation rounds). Only in `config="full"`.

4. **Orchestrator: ablation configs** — `solo`, `two_agent`, `three_agent`, `full` map to which agents run and whether sprint-contract fires. Single code path with feature flags per config.

5. **Eval results + ablation table** — `swe-harness eval dev --config all` runs all 4 configs, writes comparison table to `eval/results/ablation-dev-<ts>.md`.

---

## Week 4 — repo-context-mcp + custom eval + caching
**Exit criteria:** Two eval tables in README; prompt caching live; custom eval running.

### Tasks

1. **`src/repo_context_mcp/git_backend.py`** — `list_recent_commits(repo_path, n)`: `git log --oneline -n`. No AST.

2. **`src/repo_context_mcp/tree_sitter_backend.py`** — `get_test_for_function(repo_path, func_name)`: tree-sitter Python grammar, pattern-match test functions referencing `func_name`.

3. **`src/repo_context_mcp/jedi_backend.py`** — `find_definition(repo_path, file, line, col)`, `find_usages(repo_path, file, line, col)`: jedi Script API.

4. **`src/repo_context_mcp/server.py`** — MCP stdio server wiring all 4 tools. Registered in Reproducer + Generator only (Evaluator excluded per ADR 0004).

5. **Prompt caching in `base.py`** — unconditionally wrap system prompt + every repo file block in `cache_control: ephemeral` (ADR 0005). Stable prefix order: system → repo context → task instructions.

6. **`eval/datasets/custom/`** — 15 custom OSS bug manifests. Each: `repo_url, commit, issue_url, gold_patch_url, gold_tests[]`.

7. **`swe-harness eval custom`** — same CLI pattern as dev. Grading: run gold tests against harness patch.

8. **Budget hard-kill wiring** — orchestrator catches `BudgetExceeded`, writes partial `RunRecord` with `status=budget_exceeded`, tears down container cleanly.

---

## Week 5 — SWE-bench Verified + traces CLI + OSS PRs
**Exit criteria:** Verified pass@1 numbers (n=30); `swe-harness traces show` works; ≥5 PR links recorded.

### Tasks

1. **SWE-bench Docker integration** — orchestrator `config="swebench"` uses official SWE-bench Docker images instead of generic Python 3.11 image. Instance IDs → image tags via `swebench_manifests.json`.

2. **`eval/datasets/swebench/`** — 30 instance IDs, stratified by difficulty. Script to pull official Docker images.

3. **`swe-harness eval swebench`** — runs solo + full configs only (budget constraint from PRD). Writes `eval/results/swebench-<ts>.json`.

4. **`cli.py` traces command** — `swe-harness traces show <run-id>`: reads `runs/<run-id>/trace.ndjson`, renders table via Rich: ts, agent, event, tokens, cost, duration.

5. **OSS PR workflow** — Generator produces `pr_description.md` alongside patch. Template: bug description, fix approach, test added, provenance disclosure. Orchestrator writes to run dir; human reviews before submission.

---

## Week 6 — Failure analysis + README + polish
**Exit criteria:** Repo presentable to recruiters; FAILURES.md; reproducibility instructions.

### Tasks

1. **`FAILURES.md`** — 5 post-mortems on representative failures from eval runs. Format: issue, what the harness did, root cause, what would fix it.

2. **README rewrite** — engineering blog post format: problem → architecture → results (ablation tables) → limitations → what's next. Pull final numbers from `eval/results/`.

3. **Reproducibility section** — pinned instance IDs, exact model versions (`claude-sonnet-4-6`, `claude-haiku-4-5-20251001`), harness git SHA, run date, Docker image versions.

4. **`eval/results/` final tables** — markdown ablation tables for dev + custom; SWE-bench pass@1 table; cost/latency summary.

5. **Demo recording** — 5-min narrated screen capture of `swe-harness run` on a real issue end-to-end.

---

## Key invariants to enforce throughout

- Generator **never** modifies files under `tests/` of the target repo (enforced in Evaluator hack check + system prompt constraint).
- Evaluator **never** receives gold patch (orchestrator does not pass it; Evaluator only sees diff + test results).
- All exceptions surface or re-raise with context — no swallowing.
- Every new top-level dep flagged in response before adding to pyproject.toml.
- `pytest` output pasted before claiming any task complete.

## Verification per week

Each week's tasks are complete when:
1. `uv run pytest` passes (no skips).
2. `uv run mypy src/` passes (strict).
3. End-to-end CLI command from that week's exit criteria runs without error on a real input.
