# PRD: `swe-harness`

**A multi-agent harness for autonomous bug-fixing on Python repositories.**

|                      |                         |
| -------------------- | ----------------------- |
| **Owner**            | CJ                      |
| **Status**           | Draft v1                |
| **Last updated**     | 2026-04-29              |
| **Target ship date** | 6 weeks from kickoff    |
| **Project type**     | Portfolio / open-source |

---

## 1. Summary

`swe-harness` is a multi-agent system that takes a GitHub issue describing a bug in a Python repository and produces a pull request containing a fix and a regression test. It is built around a three-agent architecture — Reproducer, Generator, Evaluator — inspired by Anthropic's published work on long-running agent harnesses.

The project's purpose is twofold: (1) demonstrate competitive AI Engineering skills through a credible, evaluable artifact, and (2) produce real, merged contributions to open-source Python projects as proof of usefulness.

## 2. Problem statement

Current AI coding assistants are optimized for single-turn, in-IDE assistance. Autonomous bug-fixing — taking an issue and producing a mergeable PR with no human in the loop — remains an open problem characterized by three persistent failure modes:

1. **Premature victory.** Single agents often declare a fix done after partial work, without verifying behavior end-to-end.
2. **Self-evaluation blindness.** Agents asked to grade their own output tend toward sycophantic approval, even on obviously poor work.
3. **Context exhaustion.** Long-running coding tasks blow through context windows, and naive compaction loses critical state about what has been tried.

A well-designed harness — explicit role separation, structured handoffs, skeptical evaluation — can substantially close the gap between raw model capability and autonomous task completion.

## 3. Goals & non-goals

### Goals

- Build a working three-agent harness that fixes bugs autonomously end-to-end.
- Evaluate rigorously across three eval sets: 10-bug dev set, 15-bug custom OSS eval, 30-instance SWE-bench Verified sample.
- Run a meaningful ablation study isolating the contribution of each agent role.
- Submit at least 5 real PRs to active Python OSS projects; aim for 1-3 merged within the project window.
- Ship a public repo with engineering-grade documentation: failure analysis, ablation tables, cost/latency data, reproducibility instructions.

### Non-goals

- Beating state-of-the-art on SWE-bench leaderboards.
- Supporting languages other than Python (v1).
- Building a web UI, IDE plugin, or hosted service.
- Fine-tuning or training any models.
- Implementing a real-time observability dashboard.
- Multi-repo or codebase-wide refactor scenarios.

## 4. Success metrics

| Metric                                      | Target                                |
| ------------------------------------------- | ------------------------------------- |
| Pass@1 on 10-bug dev set (full harness)     | ≥50%                                  |
| Pass@1 on 15-bug custom eval (full harness) | ≥30%                                  |
| Pass@1 on SWE-bench Verified sample (n=30)  | ≥20%                                  |
| Ablation: full harness vs. solo baseline    | ≥10pp absolute improvement on dev set |
| OSS PRs submitted                           | ≥5                                    |
| OSS PRs merged within project window        | ≥1                                    |
| Total API spend                             | ≤$200                                 |
| Average cost per successful fix             | ≤$2.50                                |
| README + failure analysis published         | Yes                                   |

Stretch: published blog post; >100 GitHub stars within 30 days of release.

## 5. Users

**Primary:** Hiring managers and senior engineers evaluating CJ for AI Engineering roles. They will read the README, scan the eval tables, spot-check the code, and look for evidence of design judgment.

**Secondary:** OSS maintainers receiving PRs. They will read the PR description and diff. They care about correctness, clarity, and honesty about provenance.

**Tertiary:** Other AI engineers who find the repo. They will look for reusable patterns and ablation insights.

## 6. Architecture

### 6.1 Agent roles

Three specialized agents communicate via structured JSON artifacts on disk. No agent has more than one role.

**Reproducer (Planner-equivalent).** Reads the issue, explores the repo, locates or writes a failing test that captures the bug, and runs it to confirm it fails for the right reason. Outputs a `fix_contract.json` artifact with the failing test path, expected behavior, likely-affected files, and the reproduction command.

**Generator.** Receives `fix_contract.json` and a sandboxed checkout. Edits code, runs the failing test, iterates until the test passes. Has access to bash, file I/O, git, and the custom `repo-context-mcp` server. Bounded by a tool-call cap (50 calls) and a wall-clock timeout (15 min).

**Evaluator.** Runs after the Generator claims completion. Executes the full test suite, reviews the diff, checks for regressions and hacks (e.g., test modification instead of fix), grades against the contract, and emits a `verdict.json`. On rejection, structured feedback flows back to the Generator for up to 3 retry rounds.

### 6.2 Sprint-contract negotiation

Before the Generator codes, it proposes its approach in a short message. The Evaluator reviews the proposal and either approves or requests changes. Up to 2 negotiation rounds. This catches misunderstandings before any tokens are spent on coding — directly inspired by the contract pattern in Anthropic's harness post.

### 6.3 Sandboxing

Each task runs in a fresh Docker container: Python 3.11, git, pytest, tox, 4GB RAM cap, no network egress except PyPI. Repo checkout is mounted read-write at `/repo`. Containers are torn down on completion regardless of outcome.

### 6.4 Tools & MCP

- Built-in: bash, file read/write, git operations.
- Custom MCP server `repo-context-mcp`: `find_definition`, `find_usages`, `list_recent_commits`, `get_test_for_function`. Backed by `tree-sitter` or `jedi`.
- Standard filesystem MCP for file operations.

### 6.5 Models & cost strategy

- **Reproducer:** Sonnet 4.6 — exploration and test-writing benefit from stronger reasoning.
- **Generator:** Haiku 4.5 by default; Sonnet 4.6 for SWE-bench Verified runs where difficulty justifies the cost.
- **Evaluator:** Sonnet 4.6 — must be skeptical and capable of catching subtle hacks.
- **Opus 4.7:** held in reserve for hard cases only.
- **Prompt caching** is mandatory on system prompts and any repo file loaded more than once. Targeted savings: 40-60% on Generator costs.

### 6.6 Logging

Every tool call, model call, token count, and dollar amount is logged to a structured JSON trace file per run. SQLite for aggregated eval results. Traces are inspected via a CLI viewer (`swe-harness traces show <run-id>`).

## 7. Evaluation plan

### 7.1 Dev set (n=10)

10 bugs sampled from SWE-bench Verified, mixing easy and medium difficulty. Used during weeks 1-3 for fast iteration. Pinned commits, reproducible.

### 7.2 Custom OSS eval (n=15)

15 bugs from active Python OSS projects _not_ in SWE-bench, sourced from closed issues with linked merging PRs. Each instance includes the parent commit, gold patch, and a one-line expected-fix description. Grading: run gold tests against the harness's patch.

### 7.3 SWE-bench Verified sample (n=30)

30-instance stratified sample from SWE-bench Verified, evaluated using the official SWE-bench Docker images for ground-truth grading. Methodology disclosed: instance IDs, model versions, harness git SHA, date.

### 7.4 Ablation matrix

Run the following four configurations on the 10-bug dev set and the 15-bug custom eval:

| Config                    | Reproducer | Generator | Evaluator | Contract |
| ------------------------- | ---------- | --------- | --------- | -------- |
| Solo baseline             | —          | ✓         | —         | —        |
| Two-agent                 | ✓          | ✓         | —         | —        |
| Three-agent (no contract) | ✓          | ✓         | ✓         | —        |
| Full harness              | ✓          | ✓         | ✓         | ✓        |

For SWE-bench Verified, run only solo baseline and full harness due to budget.

### 7.5 Real OSS PRs

5 PRs to friendly Python repos with "good first issue" labels (candidates: `httpx`, `pydantic`, `click`, `rich`, `typer`, smaller libs). Each PR includes a transparent description that the patch was agent-generated and human-reviewed.

## 8. Scope & milestones

| Week | Milestone                                                  | Exit criteria                                       |
| ---- | ---------------------------------------------------------- | --------------------------------------------------- |
| 1    | Solo baseline running in sandbox                           | End-to-end run on a real issue with full traces     |
| 2    | Two-agent system + first ablation                          | Reproducer + Generator beats solo on 10-bug dev set |
| 3    | Three-agent system + contract negotiation                  | Full ablation table on dev set                      |
| 4    | Custom 15-bug eval + custom MCP server + cost optimization | Two eval tables in README; caching live             |
| 5    | SWE-bench Verified n=30 + 5 OSS PRs submitted              | Verified pass@1 numbers; PR links recorded          |
| 6    | Failure analysis, README rewrite, demo recording           | Repo presentable to recruiters                      |

## 9. Budget

Total API budget: **$200**.

| Bucket                    | Allocation |
| ------------------------- | ---------- |
| Development & debugging   | $60        |
| Custom eval runs          | $50        |
| SWE-bench Verified sample | $60        |
| OSS PR attempts           | $20        |
| Buffer                    | $10        |

Hard guardrails: API key budget alerts at $50, $100, $150. Tool-call caps and wall-clock timeouts on every agent. Early-termination logic on stalled runs.

## 10. Risks & mitigations

| Risk                                                  | Likelihood | Impact | Mitigation                                                                                                    |
| ----------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------------- |
| API costs blow past $200                              | Medium     | High   | Aggressive caching, Haiku-first, tool-call caps, budget alerts                                                |
| Pass rates too low to tell a story                    | Medium     | High   | Stratified dev set; if numbers are bad, lead the README with ablation deltas instead of absolute numbers      |
| Evaluator becomes a rubber stamp                      | Medium     | High   | Few-shot calibration with hand-written bad-fix examples; spot-check 20% of "passes" manually                  |
| OSS maintainers reject all PRs                        | Medium     | Medium | Submit to multiple repos; honest provenance disclosure; manually polish before submit                         |
| SWE-bench Docker setup eats a week                    | Medium     | Medium | Allocate buffer in week 5; fall back to running on the custom eval only if blocked                            |
| Scope creep (UI, multi-language, fine-tuning)         | High       | High   | This PRD is the contract; non-goals are non-negotiable for v1                                                 |
| Models improve mid-project, harness becomes redundant | Low        | Low    | Re-run ablations on new models for a "harness is now over-engineered" follow-up post — itself a strong signal |

## 11. Deliverables

A public GitHub repo containing:

- Three-agent harness in idiomatic Python (~3-5k LOC).
- One custom MCP server (`repo-context-mcp`) with its own README.
- CLI: `swe-harness run <issue>`, `swe-harness eval <set>`, `swe-harness traces show <id>`.
- Three eval result sets with ablations, in markdown tables and raw JSON.
- `FAILURES.md`: 5 detailed post-mortems on representative failures.
- README written as an engineering blog post: problem, architecture, results, limitations, what's next.
- 5-minute narrated screen recording of an end-to-end run.
- Reproducibility instructions: pinned commits, model versions, exact prompts.
- Optional: blog post on personal site / HN submission.

## 12. Open questions

1. Should the Evaluator have access to the gold patch when grading on SWE-bench? _Default: no — would invalidate the eval._
2. How aggressively should the Generator be allowed to modify tests? _Default: forbidden to modify pre-existing tests; may add new ones._
3. Should retries on Evaluator rejection use the same model or escalate to Opus? _Default: same model; escalation is a stretch experiment._
4. Cutoff for what counts as a "merged" PR for success metrics? _Default: any merge to default branch within 30 days of submission._

## 13. Out of scope (explicit non-goals, restated)

- Languages other than Python.
- Web UI, IDE plugin, hosted service.
- Model fine-tuning.
- Real-time dashboards.
- Multi-repo / cross-codebase refactors.
- Beating SOTA.
- Synthetic/generated bugs (real issues only).

## 14. References

- Anthropic Engineering, _Effective harnesses for long-running agents_ (Nov 2025).
- Anthropic Engineering, _Harness design for long-running application development_ (Mar 2026).
- SWE-bench: Jimenez et al., _SWE-bench: Can Language Models Resolve Real-World GitHub Issues?_
- Claude Agent SDK documentation.
- Model Context Protocol specification.

---

_This PRD is the project's source of truth. Changes to scope, success metrics, or non-goals require a dated revision note appended below._

## Revision history

- **v1 (2026-04-29):** Initial draft.
