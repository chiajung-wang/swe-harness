# swe-harness

> **Status: In development** — data models, budget accumulator, and trace writer implemented; orchestrator, agents, and MCP server pending

Multi-agent harness for autonomous Python bug-fixing. Takes a GitHub issue, produces a PR with a fix and regression test.

## Architecture

Three agents communicate via structured JSON artifacts on disk:

| Agent          | Model      | Responsibility                                                |
| -------------- | ---------- | ------------------------------------------------------------- |
| **Reproducer** | Sonnet 4.6 | Reads issue → writes failing test → emits `fix_contract.json` |
| **Generator**  | Haiku 4.5  | Receives contract → edits code → iterates until test passes   |
| **Evaluator**  | Sonnet 4.6 | Runs full suite → checks for hacks → emits `verdict.json`     |

Generator is bounded by a 50-call tool cap and 15-minute wall-clock timeout. Evaluator can reject and feed structured feedback back to Generator (max 3 rounds). Before any code changes, Generator proposes its approach and Evaluator must approve (sprint-contract negotiation).

Each task runs in an isolated Docker container (Python 3.11, no network except PyPI). The orchestrator manages the container lifecycle; agents run outside via `docker exec`. The container is reused across retry rounds so Generator can build on partial work. A custom MCP server (`repo-context-mcp`) provides code-navigation tools backed by jedi (definitions/usages), tree-sitter (test lookup), and git (commits).

## Usage

```bash
swe-harness run <issue-url>      # end-to-end fix attempt
swe-harness eval <set>           # run eval set: dev | custom | swebench
swe-harness traces show <run-id> # inspect structured trace
```

## Setup

```bash
uv sync
```

Requires Docker. Set `ANTHROPIC_API_KEY` in your environment.

## Eval sets

| Set      | n   | Source                               |
| -------- | --- | ------------------------------------ |
| dev      | 10  | SWE-bench Verified (pinned commits)  |
| custom   | 15  | Real OSS bugs not in SWE-bench       |
| swebench | 30  | SWE-bench Verified stratified sample |

## Architecture docs

- [`CONTEXT.md`](CONTEXT.md) — canonical glossary, resolved decisions, artifact schemas
- [`docs/adr/`](docs/adr/) — architecture decision records

## Results

_Not yet available — results will be published after week 3._
