## What to build

Implement `src/swe_harness/docker_manager.py` — container lifecycle manager. Spins up a Python 3.11 Docker container with the target repo, executes commands inside it, and tears it down. Container is reused across rounds; teardown is the orchestrator's responsibility.

## Acceptance criteria

- [ ] `DockerManager` with `start(repo_url: str, commit: str) -> str` (returns container ID)
- [ ] `start()` clones repo at `commit` into `/repo` inside container
- [ ] Container spec: Python 3.11, git, pytest, tox, 4 GB RAM limit, no network except PyPI
- [ ] `exec(cmd: str) -> tuple[str, str]` returns `(stdout, stderr)`; raises on non-zero exit
- [ ] `stop()` removes container; idempotent if already stopped
- [ ] Container instance reused across multiple `exec()` calls (not re-created per call)
- [ ] Integration test (skipped if Docker unavailable): start → exec `python --version` → stop
- [ ] `uv run pytest` passes
- [ ] `uv run mypy src/` passes (strict)

## Blocked by

- `01-core-data-models.md` (type imports)
