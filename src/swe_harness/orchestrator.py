from __future__ import annotations

import datetime
import logging
import re
import time
from pathlib import Path
from typing import Callable, Literal

from swe_harness.agents.generator import Generator, StallDetected, TimeoutExceeded, ToolCapExceeded
from swe_harness.budget import Budget, BudgetExceeded
from swe_harness.db import init_db, upsert_run
from swe_harness.docker_manager import DockerManager
from swe_harness.models import FixContract, RunRecord
from swe_harness.tracer import Tracer

logger = logging.getLogger(__name__)

_BUDGET_LIMIT = 200.0
_RUNS_DIR = Path("runs")

Config = Literal["solo", "two_agent", "three_agent", "full"]
ProgressReporter = Callable[[str], None]


def _run_id(issue_url: str) -> str:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S")
    # Derive a short slug from the URL path: owner-repo-issuenum
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", issue_url.rstrip("/").split("//")[-1])
    slug = slug.strip("-")[:60]
    return f"{ts}-{slug}"


def _repo_url_from_issue(issue_url: str) -> str:
    # https://github.com/owner/repo/issues/N  →  https://github.com/owner/repo
    match = re.match(r"(https?://[^/]+/[^/]+/[^/]+)/issues/", issue_url)
    if match:
        return match.group(1)
    raise ValueError(f"Cannot derive repo URL from issue URL: {issue_url!r}")


def run(
    issue_url: str,
    fix_contract: FixContract,
    config: Config = "solo",
    runs_dir: Path = _RUNS_DIR,
    reporter: ProgressReporter | None = None,
) -> RunRecord:
    """Run the harness against one issue, returning the completed RunRecord.

    Creates a run directory, starts Docker, runs the Generator (solo config),
    persists the RunRecord to SQLite, and always tears down the container.
    """
    reporter = reporter or (lambda _: None)

    run_id = _run_id(issue_url)
    run_dir = runs_dir / run_id
    db_path = runs_dir / "harness.db"

    init_db(db_path)

    tracer = Tracer(run_dir)
    budget = Budget(_BUDGET_LIMIT)
    docker = DockerManager()

    wall_start = time.monotonic()
    verdict: Literal["pass", "fail"] | None = None
    rounds = 0

    repo_url = _repo_url_from_issue(issue_url)

    try:
        docker_start = time.monotonic()
        reporter(f"◆ Docker starting (repo={repo_url} commit={fix_contract.repo_commit})")
        docker.start(repo_url, fix_contract.repo_commit)
        reporter(f"◆ Docker ready ({time.monotonic() - docker_start:.1f}s)")
        reporter("◆ Generator started")

        generator = Generator(
            fix_contract=fix_contract,
            run_dir=run_dir,
            docker=docker,
            tracer=tracer,
            budget=budget,
            reporter=reporter,
        )

        rounds = 1
        try:
            generator.run()
            verdict = "pass"
            reporter("◆ Repro passed — done")
        except (ToolCapExceeded, TimeoutExceeded, StallDetected) as exc:
            logger.warning("run=%s generator terminated: %s", run_id, exc)
            verdict = "fail"
            reporter(f"◆ Repro failed — {type(exc).__name__}")

    except BudgetExceeded as exc:
        logger.error("run=%s budget exceeded: %s", run_id, exc)
        verdict = None  # partial run
        reporter("◆ Budget exceeded")

    finally:
        docker.stop()

    duration_s = time.monotonic() - wall_start
    record = RunRecord(
        run_id=run_id,
        issue_url=issue_url,
        config=config,
        verdict=verdict,
        rounds=rounds,
        cost_usd=budget.spent,
        duration_s=round(duration_s, 3),
        ts=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )
    upsert_run(record, db_path)
    logger.info("run=%s done verdict=%s cost=$%.4f", run_id, verdict, budget.spent)
    return record
