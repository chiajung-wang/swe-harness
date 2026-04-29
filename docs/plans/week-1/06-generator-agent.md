## What to build

Implement `src/swe_harness/agents/generator.py` — the core coding agent. Reads `fix_contract.json`, runs an agentic loop to patch the repo inside Docker, and exits when the failing test passes or a cap is hit. No sprint-contract negotiation yet (week 3).

## Acceptance criteria

- [ ] `Generator(fix_contract: FixContract, run_dir: Path, docker: DockerManager, tracer: Tracer, budget: Budget)`
- [ ] Agentic loop: reads `fix_contract.json` from `run_dir`, iterates tool calls until repro command passes
- [ ] Hard caps: 50 tool calls, 15-minute wall-clock timeout; raises descriptive exception on breach
- [ ] Stall detection aborts loop: identical tool call ×3, same file patch ×5, 60 s idle
- [ ] Writes patch via `docker.exec()` — does NOT modify files under `tests/` of target repo
- [ ] System prompt + repo file blocks unconditionally wrapped with `_build_cache_block()` (ADR 0005)
- [ ] `uv run pytest` passes
- [ ] `uv run mypy src/` passes (strict)

## Blocked by

- `04-docker-sandbox.md`
- `05-anthropic-agent-base.md`
