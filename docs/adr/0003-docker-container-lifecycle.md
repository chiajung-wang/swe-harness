# ADR 0003: Docker container lifecycle

**Status:** Accepted  
**Date:** 2026-04-29

## Decisions

1. **Orchestrator manages containers from outside** — Python orchestrator spins up and tears down containers; agents are not aware they're in Docker.
2. **Agents run outside the container** — Generator issues commands via `docker exec`; no Python agent code runs inside the container.
3. **One container per run, reused across retry rounds** — Generator's partial work persists between Evaluator rejection rounds. Fresh container per new issue.

## Rationale

**Outside management:** Clean separation of concerns. Orchestrator can enforce wall-clock timeout and kill runaway containers without relying on in-container logic.

**Agents outside:** Avoids duplicating the Python environment inside the container. All agent code runs in one place. `docker exec` is sufficient for bash, file I/O, and git.

**Reuse across rounds:** Avoids re-cloning the repo and re-installing dependencies on every retry. Generator can build on previous partial work. Container is still isolated from the host.
