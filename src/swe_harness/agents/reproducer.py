from __future__ import annotations

import base64
from pathlib import Path, PurePosixPath
from typing import Callable

from anthropic.types import (
    ContentBlockParam,
    MessageParam,
    TextBlockParam,
    ToolResultBlockParam,
    ToolUseBlock,
    ToolUnionParam,
)

from swe_harness.agents.base import AnthropicAgent
from swe_harness.budget import Budget
from swe_harness.docker_manager import CommandError, DockerManager
from swe_harness.models import FixContract
from swe_harness.tracer import Tracer

_MODEL = "claude-sonnet-4-6"
_TOOL_CAP = 20
_FORCED_INJECT_AT = 17

_FORCED_INJECT_TEXT = (
    "You are near your tool call limit. "
    "Call `emit_contract` now with your best current understanding of the bug."
)


class ToolCapExceeded(Exception):
    """Raised when the 20-call cap is hit without a valid emit_contract."""


class StallDetected(Exception):
    """Raised when the model stops issuing tool calls without emitting a contract."""


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
            "Overwrite a source file in the repo at /repo. "
            "Cannot write to paths under tests/ — use write_test for that."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to /repo (tests/ blocked)"},
                "content": {"type": "string", "description": "Full file content"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "write_test",
        "description": "Write a test file under tests/ in the repo at /repo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to /repo, must start with tests/"},
                "content": {"type": "string", "description": "Full test file content"},
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
    {
        "name": "emit_contract",
        "description": (
            "Finalize and emit the fix contract. Call this when you have written a failing test "
            "and confirmed it exits non-zero. This ends your session."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "failing_test": {
                    "type": "string",
                    "description": "pytest node ID, e.g. tests/test_foo.py::test_bar",
                },
                "repro_command": {
                    "type": "string",
                    "description": "Shell command that exits non-zero on the bug",
                },
                "expected_behavior": {"type": "string"},
                "likely_affected_files": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "error_output": {
                    "type": "string",
                    "description": "Captured output from the failing test run",
                },
                "reproducer_confidence": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                },
            },
            "required": [
                "failing_test",
                "repro_command",
                "expected_behavior",
                "likely_affected_files",
                "error_output",
                "reproducer_confidence",
            ],
        },
    },
]


class Reproducer(AnthropicAgent):
    """Explores a repo, writes a failing test, and emits a FixContract.

    Accepts issue_url + repo_commit as ground truth; the model never supplies
    these — they are injected into the initial message and written by the system.
    """

    def __init__(
        self,
        issue_url: str,
        repo_commit: str,
        issue_body: str,
        run_dir: Path,
        docker: DockerManager,
        tracer: Tracer,
        budget: Budget,
        reporter: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(
            model=_MODEL,
            run_id=run_dir.name,
            tracer=tracer,
            budget=budget,
        )
        self._issue_url = issue_url
        self._repo_commit = repo_commit
        self._issue_body = issue_body
        self._run_dir = run_dir
        self._docker = docker
        self._reporter = reporter or (lambda _: None)
        self._test_confirmed_failing = False

    def run(self) -> FixContract:
        """Run the agentic loop until a contract is emitted or the cap is hit.

        Returns the emitted FixContract on success.
        Raises ToolCapExceeded after writing a low-confidence fallback contract.
        Raises StallDetected if the model stops issuing tool calls.
        """
        tool_call_count = 0
        forced_inject_sent = False
        call_num = 0

        system = self._build_system_prompt()
        messages: list[MessageParam] = [
            {
                "role": "user",
                "content": [
                    TextBlockParam(
                        type="text",
                        text=self._build_initial_message(),
                        cache_control={"type": "ephemeral"},
                    )
                ],
            }
        ]

        while True:
            response, entry = self._call(system=system, messages=messages, tools=_TOOLS)
            call_num += 1
            self._reporter(
                f"  [{call_num}] model call → {entry.input_tokens} in / {entry.output_tokens} out"
                f"  ${entry.cost_usd:.4f}"
            )
            messages.append({"role": "assistant", "content": response.content})

            tool_uses = [b for b in response.content if isinstance(b, ToolUseBlock)]

            if not tool_uses:
                raise StallDetected(
                    "Reproducer stopped issuing tool calls without emitting a contract"
                )

            tool_results: list[ContentBlockParam] = []
            emitted_contract: FixContract | None = None

            for tu in tool_uses:
                if tu.name == "emit_contract":
                    result, emitted_contract = self._handle_emit_contract(tu.input)
                    tool_results.append(
                        ToolResultBlockParam(
                            type="tool_result",
                            tool_use_id=tu.id,
                            content=result,
                        )
                    )
                    if emitted_contract is not None:
                        break
                else:
                    tool_call_count += 1
                    result = self._dispatch_tool(tu.name, tu.input)
                    self._reporter(self._format_tool_line(tu.name, tu.input, result))
                    tool_results.append(
                        ToolResultBlockParam(
                            type="tool_result",
                            tool_use_id=tu.id,
                            content=result,
                        )
                    )

            if tool_call_count >= _FORCED_INJECT_AT and not forced_inject_sent:
                forced_inject_sent = True
                tool_results.append(TextBlockParam(type="text", text=_FORCED_INJECT_TEXT))

            messages.append({"role": "user", "content": tool_results})

            if emitted_contract is not None:
                return emitted_contract

            if tool_call_count >= _TOOL_CAP:
                contract = self._build_fallback_contract()
                self._write_contract(contract)
                raise ToolCapExceeded(
                    f"Reproducer exceeded {_TOOL_CAP} tool-call cap without emitting a contract"
                )

    # ------------------------------------------------------------------
    # emit_contract
    # ------------------------------------------------------------------

    def _handle_emit_contract(
        self, inputs: object
    ) -> tuple[str, FixContract | None]:
        """Validate emit_contract inputs and write fix_contract.json on success."""
        args = inputs if isinstance(inputs, dict) else {}
        try:
            # Validate model's supplied values first — catches invalid confidence literals
            contract = FixContract.model_validate(
                {
                    "issue_url": self._issue_url,
                    "repo_commit": self._repo_commit,
                    "failing_test": str(args.get("failing_test", "")),
                    "repro_command": str(args.get("repro_command", "")),
                    "expected_behavior": str(args.get("expected_behavior", "")),
                    "likely_affected_files": list(args.get("likely_affected_files", [])),
                    "error_output": str(args.get("error_output", "")),
                    "reproducer_confidence": args.get("reproducer_confidence", "low"),
                }
            )
        except Exception as exc:
            return f"Validation error: {exc}", None

        # System override after validation: downgrade if test never confirmed failing
        if not self._test_confirmed_failing:
            contract = contract.model_copy(update={"reproducer_confidence": "low"})

        self._write_contract(contract)
        return "Contract written successfully.", contract

    def _write_contract(self, contract: FixContract) -> None:
        self._run_dir.mkdir(parents=True, exist_ok=True)
        (self._run_dir / "fix_contract.json").write_text(contract.model_dump_json(indent=2))

    def _build_fallback_contract(self) -> FixContract:
        return FixContract(
            issue_url=self._issue_url,
            repo_commit=self._repo_commit,
            failing_test="",
            repro_command="",
            expected_behavior="",
            likely_affected_files=[],
            error_output="",
            reproducer_confidence="low",
        )

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    def _dispatch_tool(self, name: str, inputs: object) -> str:
        args = inputs if isinstance(inputs, dict) else {}
        if name == "read_file":
            return self._tool_read_file(str(args.get("path", "")))
        if name == "write_file":
            return self._tool_write_file(str(args.get("path", "")), str(args.get("content", "")))
        if name == "write_test":
            return self._tool_write_test(str(args.get("path", "")), str(args.get("content", "")))
        if name == "run_command":
            return self._tool_run_command(str(args.get("command", "")))
        return f"Unknown tool: {name}"

    def _format_tool_line(self, name: str, inputs: object, result: str) -> str:
        assert isinstance(inputs, dict), f"expected dict inputs, got {type(inputs)}"
        args: dict[str, object] = inputs
        if name == "read_file":
            status = "✗" if result.startswith("Error") else "✓"
            return f"      → read_file {args.get('path', '')}  {status}"
        if name in ("write_file", "write_test"):
            status = "✓" if result.startswith("Written:") else "✗"
            return f"      → {name} {args.get('path', '')}  {status}"
        if name == "run_command":
            cmd = str(args.get("command", ""))
            short = cmd[:50] + ("…" if len(cmd) > 50 else "")
            exit_code = result.split("\n")[0].rstrip(":").lower() if result.startswith("Exit ") else "exit 0"
            return f"      → run_command {short}   {exit_code}"
        return f"      → {name}  ?"

    def _tool_read_file(self, path: str) -> str:
        path_b64 = base64.b64encode(path.encode()).decode("ascii")
        cmd = (
            "python3 -c \""
            "import base64, sys; "
            f"p='/repo/'+base64.b64decode('{path_b64}').decode(); "
            "sys.stdout.write(open(p).read())\""
        )
        try:
            stdout, _ = self._docker.exec(cmd)
            return stdout
        except CommandError as e:
            return f"Error reading {path}: {e}"

    def _tool_write_file(self, path: str, content: str) -> str:
        if any(part == "tests" for part in PurePosixPath(path).parts):
            return f"Error: use write_test to write files under tests/: {path}"
        return self._write_to_repo(path, content)

    def _tool_write_test(self, path: str, content: str) -> str:
        parts = PurePosixPath(path).parts
        if not parts or parts[0] != "tests":
            return f"Error: write_test path must start with tests/: {path}"
        return self._write_to_repo(path, content)

    def _write_to_repo(self, path: str, content: str) -> str:
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
            return out if out.strip() else "(no output)"
        except CommandError as e:
            if "pytest" in command:
                self._test_confirmed_failing = True
            return f"Exit {e.exit_code}:\n{e.stdout}\n{e.stderr}"

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        return (
            "You are an expert software engineer reproducing a bug from a GitHub issue.\n"
            "Tools: read_file, write_file (tests/ blocked), write_test (tests/ only), "
            "run_command, emit_contract.\n"
            "Steps:\n"
            "1. Explore the repository to understand the bug.\n"
            "2. Write a minimal failing test with write_test.\n"
            "3. Confirm the test fails with run_command (pytest exits non-zero).\n"
            "4. Call emit_contract with your findings.\n"
            "Do not fix the bug — only reproduce it."
        )

    def _build_initial_message(self) -> str:
        return (
            f"Reproduce the following GitHub issue.\n\n"
            f"Issue URL: {self._issue_url}\n"
            f"Repo commit: {self._repo_commit}\n\n"
            f"Issue description:\n{self._issue_body}\n\n"
            f"The repository is at /repo. Explore it, write a failing test under tests/, "
            f"confirm it fails, then call emit_contract."
        )
