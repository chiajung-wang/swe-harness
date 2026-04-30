from __future__ import annotations

import base64
import json
import time
from collections import deque
from pathlib import Path

from anthropic.types import MessageParam, ToolResultBlockParam, ToolUseBlock, ToolUnionParam

from swe_harness.agents.base import AnthropicAgent
from swe_harness.budget import Budget
from swe_harness.docker_manager import CommandError, DockerManager
from swe_harness.models import FixContract
from swe_harness.tracer import Tracer

_MODEL = "claude-haiku-4-5-20251001"
_TOOL_CAP = 50
_TIMEOUT_S = 15 * 60  # 15 minutes
_IDLE_S = 60
_STALL_CALL_CAP = 3   # abort if last N tool calls are identical
_STALL_PATCH_CAP = 5  # abort if any single file is patched this many times


class ToolCapExceeded(Exception):
    """Raised when the 50-call tool cap is breached."""


class TimeoutExceeded(Exception):
    """Raised when the 15-minute wall-clock limit is breached."""


class StallDetected(Exception):
    """Raised when the agentic loop stops making progress."""


_TOOLS: list[ToolUnionParam] = [
    {
        "name": "read_file",
        "description": "Read a file from the repo at /repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to /repo"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": (
            "Overwrite a file in the repo at /repo. "
            "Cannot modify any path under tests/."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to /repo"},
                "content": {"type": "string", "description": "Full file content"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command inside /repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
            },
            "required": ["command"],
        },
    },
]


class Generator(AnthropicAgent):
    """Agentic coding agent that patches a repo inside Docker to fix a bug.

    Iterates tool calls (read/write/run) until the repro command passes,
    a hard cap is hit, or a stall is detected.
    """

    def __init__(
        self,
        fix_contract: FixContract,
        run_dir: Path,
        docker: DockerManager,
        tracer: Tracer,
        budget: Budget,
    ) -> None:
        super().__init__(
            model=_MODEL,
            run_id=run_dir.name,
            tracer=tracer,
            budget=budget,
        )
        self._fix_contract = fix_contract
        self._run_dir = run_dir
        self._docker = docker

    def run(self) -> None:
        """Run the agentic fix loop until repro passes or a cap is hit."""
        wall_start = time.monotonic()
        tool_call_count = 0
        # Tracks the last N tool-call signatures for identical-call stall detection
        recent_call_keys: deque[str] = deque(maxlen=_STALL_CALL_CAP)
        # Tracks how many times each file has been patched
        patch_counts: dict[str, int] = {}
        # Time of the last successful tool execution (for idle stall detection)
        last_tool_exec = time.monotonic()

        system = [self._build_cache_block(self._build_system_prompt())]
        messages: list[MessageParam] = [
            {"role": "user", "content": self._build_initial_message()}
        ]

        while True:
            if time.monotonic() - wall_start > _TIMEOUT_S:
                raise TimeoutExceeded(
                    f"Generator exceeded {_TIMEOUT_S // 60}-minute wall-clock limit"
                )

            if time.monotonic() - last_tool_exec > _IDLE_S:
                raise StallDetected(
                    f"No tool execution in {_IDLE_S}s — loop is idle"
                )

            response = self._call(system=system, messages=messages, tools=_TOOLS)
            messages.append({"role": "assistant", "content": response.content})

            tool_uses = [b for b in response.content if isinstance(b, ToolUseBlock)]

            if not tool_uses:
                if self._repro_passes():
                    return
                raise StallDetected(
                    "Model stopped issuing tool calls but repro command still fails"
                )

            tool_results: list[ToolResultBlockParam] = []
            for tu in tool_uses:
                # Identical-call stall: abort if last N calls are all the same
                call_key = f"{tu.name}:{json.dumps(tu.input, sort_keys=True)}"
                recent_call_keys.append(call_key)
                if (
                    len(recent_call_keys) == _STALL_CALL_CAP
                    and len(set(recent_call_keys)) == 1
                ):
                    raise StallDetected(
                        f"Tool call '{tu.name}' repeated {_STALL_CALL_CAP}× identically"
                    )

                result = self._dispatch_tool(tu.name, tu.input, patch_counts)
                tool_results.append(
                    ToolResultBlockParam(
                        type="tool_result",
                        tool_use_id=tu.id,
                        content=result,
                    )
                )

            messages.append({"role": "user", "content": tool_results})
            last_tool_exec = time.monotonic()
            tool_call_count += len(tool_uses)

            if tool_call_count >= _TOOL_CAP:
                raise ToolCapExceeded(
                    f"Generator exceeded {_TOOL_CAP} tool-call cap"
                )

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    def _dispatch_tool(
        self,
        name: str,
        inputs: object,
        patch_counts: dict[str, int],
    ) -> str:
        args = inputs if isinstance(inputs, dict) else {}
        if name == "read_file":
            return self._tool_read_file(str(args.get("path", "")))
        if name == "write_file":
            return self._tool_write_file(
                str(args.get("path", "")),
                str(args.get("content", "")),
                patch_counts,
            )
        if name == "run_command":
            return self._tool_run_command(str(args.get("command", "")))
        return f"Unknown tool: {name}"

    def _tool_read_file(self, path: str) -> str:
        try:
            stdout, _ = self._docker.exec(f"cat /repo/{path}")
            return stdout
        except CommandError as e:
            return f"Error reading {path}: {e}"

    def _tool_write_file(
        self, path: str, content: str, patch_counts: dict[str, int]
    ) -> str:
        if path.startswith("tests/") or path == "tests":
            return f"Error: Generator may not modify test files: {path}"

        patch_counts[path] = patch_counts.get(path, 0) + 1
        if patch_counts[path] >= _STALL_PATCH_CAP:
            raise StallDetected(
                f"File patched {_STALL_PATCH_CAP}× without progress: {path}"
            )

        # Encode both path and content as base64 so neither is interpolated
        # into the shell string — avoids injection from model-generated content.
        path_b64 = base64.b64encode(path.encode()).decode("ascii")
        content_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        cmd = (
            "python3 -c \""
            "import base64, os; "
            f"p='/repo/'+base64.b64decode('{path_b64}').decode(); "
            "os.makedirs(os.path.dirname(p) or '.', exist_ok=True); "
            f"open(p,'w').write(base64.b64decode('{content_b64}').decode('utf-8'))\""
        )
        try:
            self._docker.exec(cmd)
            return f"Written: {path}"
        except CommandError as e:
            return f"Error writing {path}: {e}"

    def _tool_run_command(self, command: str) -> str:
        try:
            stdout, stderr = self._docker.exec(command)
            out = stdout + (f"\nstderr: {stderr}" if stderr.strip() else "")
            return out or "(no output)"
        except CommandError as e:
            return f"Exit {e.exit_code}:\n{e.stdout}\n{e.stderr}"

    # ------------------------------------------------------------------
    # Repro check and prompt builders
    # ------------------------------------------------------------------

    def _repro_passes(self) -> bool:
        try:
            self._docker.exec(self._fix_contract.repro_command)
            return True
        except CommandError:
            return False

    def _build_system_prompt(self) -> str:
        return (
            "You are an expert Python developer fixing a bug in a repository.\n"
            "Tools available: read_file, write_file, run_command.\n"
            "Constraint: do NOT modify any file under the tests/ directory.\n"
            "Goal: make the repro command exit 0 with a minimal, correct patch.\n"
            "When you believe the fix is complete, stop issuing tool calls."
        )

    def _build_initial_message(self) -> str:
        fc = self._fix_contract
        return (
            f"Fix the following bug.\n\n"
            f"Issue: {fc.issue_url}\n"
            f"Expected behavior: {fc.expected_behavior}\n"
            f"Repro command: {fc.repro_command}\n"
            f"Failing test: {fc.failing_test}\n"
            f"Likely affected files: {', '.join(fc.likely_affected_files)}\n"
            f"Error output:\n{fc.error_output}\n\n"
            f"Start by reading the relevant files, then apply a minimal fix."
        )
