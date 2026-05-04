from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel

from swe_harness import orchestrator
from swe_harness.models import FixContract

console = Console()

logging.basicConfig(
    level=logging.WARNING,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, show_path=False)],
)


@click.group()
def main() -> None:
    """swe-harness: autonomous Python bug-fixing harness."""


@main.command("run")
@click.argument("issue_url")
@click.option(
    "--fix-contract",
    "fix_contract_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to fix_contract.json produced by the Reproducer.",
)
@click.option(
    "--config",
    default="solo",
    type=click.Choice(["solo", "two_agent", "three_agent", "full"]),
    show_default=True,
    help="Agent configuration to use.",
)
def run_cmd(issue_url: str, fix_contract_path: Path, config: str) -> None:
    """Run the harness against ISSUE_URL and write a fix."""
    try:
        fix_contract = FixContract.model_validate(
            json.loads(fix_contract_path.read_text())
        )
    except Exception as exc:
        console.print(f"[red]Error loading fix contract:[/red] {exc}")
        sys.exit(1)

    console.print(Panel(
        f"[bold]Issue:[/bold] {issue_url}\n"
        f"[bold]Config:[/bold] {config}\n"
        f"[bold]Commit:[/bold] {fix_contract.repo_commit}",
        title="swe-harness run",
        expand=False,
    ))

    try:
        record = orchestrator.run(
            issue_url=issue_url,
            fix_contract=fix_contract,
            config=config,  # type: ignore[arg-type]
            reporter=lambda s: console.print(s, markup=False),
        )
    except (ValueError, Exception) as exc:
        console.print(f"[red]Run failed:[/red] {exc}")
        sys.exit(1)

    verdict_style = "green" if record.verdict == "pass" else "yellow" if record.verdict is None else "red"
    console.print(Panel(
        f"[bold]Run ID:[/bold]   {record.run_id}\n"
        f"[bold]Verdict:[/bold]  [{verdict_style}]{record.verdict}[/{verdict_style}]\n"
        f"[bold]Cost:[/bold]     ${record.cost_usd:.4f}\n"
        f"[bold]Duration:[/bold] {record.duration_s:.1f}s",
        title="Result",
        expand=False,
    ))
