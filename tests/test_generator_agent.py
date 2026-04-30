"""Unit tests for Generator agent — all Docker and Anthropic calls are mocked."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from swe_harness.agents.generator import (
    Generator,
    StallDetected,
    TimeoutExceeded,
    ToolCapExceeded,
)
from swe_harness.budget import Budget
from swe_harness.docker_manager import CommandError
from swe_harness.models import FixContract
from swe_harness.tracer import Tracer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fix_contract() -> FixContract:
    return FixContract(
        issue_url="https://github.com/example/repo/issues/1",
        repo_commit="abc123",
        failing_test="test_example.py::test_bug",
        repro_command="pytest test_example.py::test_bug",
        expected_behavior="Should return 42",
        likely_affected_files=["src/module.py"],
        error_output="AssertionError: 0 != 42",
        reproducer_confidence="high",
    )


def _make_generator(tmp_path: Path) -> tuple[Generator, MagicMock, MagicMock]:
    """Return (generator, docker_mock, client_mock) so mocks stay typed as MagicMock."""
    tracer = Tracer(tmp_path / "run")
    budget = Budget(limit_usd=10.0)
    docker: MagicMock = MagicMock()
    client: MagicMock = MagicMock()
    with patch("swe_harness.agents.base.anthropic.Anthropic"):
        gen = Generator(
            fix_contract=_fix_contract(),
            run_dir=tmp_path / "run",
            docker=docker,
            tracer=tracer,
            budget=budget,
        )
    gen._client = client
    return gen, docker, client


def _tool_use_block(name: str, inputs: dict[str, object], id: str = "tu_001") -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    # isinstance check in generator uses ToolUseBlock; patch to satisfy isinstance
    block.__class__ = __import__(
        "anthropic.types", fromlist=["ToolUseBlock"]
    ).ToolUseBlock
    block.name = name
    block.input = inputs
    block.id = id
    return block


def _usage_mock(input_tokens: int = 10, output_tokens: int = 5) -> MagicMock:
    u = MagicMock()
    u.input_tokens = input_tokens
    u.output_tokens = output_tokens
    u.cache_read_input_tokens = None
    return u


def _model_response(blocks: list[MagicMock], stop_reason: str = "tool_use") -> MagicMock:
    resp = MagicMock()
    resp.content = blocks
    resp.stop_reason = stop_reason
    resp.usage = _usage_mock()
    return resp


def _text_block(text: str = "Done.") -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_successful_run(tmp_path: Path) -> None:
    gen, docker, client = _make_generator(tmp_path)

    read_call = _tool_use_block("read_file", {"path": "src/module.py"})
    client.messages.create.side_effect = [
        _model_response([read_call]),
        _model_response([_text_block()], "end_turn"),
    ]
    docker.exec.side_effect = [
        ("def foo(): return 0\n", ""),  # read_file
        ("", ""),                        # repro passes (exit 0)
    ]

    gen.run()  # must not raise


def test_tool_cap_exceeded(tmp_path: Path) -> None:
    gen, docker, client = _make_generator(tmp_path)

    # Each model response issues 5 distinct tool calls; 10 rounds → 50 calls
    def make_response(*_args: object, **_kwargs: object) -> MagicMock:
        calls = [
            _tool_use_block("run_command", {"command": f"echo {i}"}, id=f"tu_{i}")
            for i in range(5)
        ]
        return _model_response(calls)

    client.messages.create.side_effect = make_response
    docker.exec.return_value = ("ok", "")

    with pytest.raises(ToolCapExceeded):
        gen.run()


def test_timeout_exceeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    gen, docker, client = _make_generator(tmp_path)

    # Simulate wall clock already past the limit on second check
    times = [0.0, 0.0, 99999.0]
    monkeypatch.setattr("swe_harness.agents.generator.time.monotonic", lambda: times.pop(0) if times else 99999.0)

    read_call = _tool_use_block("read_file", {"path": "f"})
    client.messages.create.return_value = _model_response([read_call])
    docker.exec.return_value = ("content", "")

    with pytest.raises(TimeoutExceeded):
        gen.run()


def test_stall_identical_tool_calls(tmp_path: Path) -> None:
    gen, docker, client = _make_generator(tmp_path)

    same_call = _tool_use_block("run_command", {"command": "echo hi"})
    client.messages.create.return_value = _model_response([same_call])
    docker.exec.return_value = ("hi", "")

    with pytest.raises(StallDetected, match="repeated"):
        gen.run()


def test_stall_same_file_patched_five_times(tmp_path: Path) -> None:
    gen, docker, client = _make_generator(tmp_path)

    # Each call patches the same file with different content so identical-call
    # stall doesn't fire, but patch-count stall fires at 5.
    call_count = 0

    def make_response(*_args: object, **_kwargs: object) -> MagicMock:
        nonlocal call_count
        call_count += 1
        write = _tool_use_block(
            "write_file",
            {"path": "src/module.py", "content": f"v{call_count}"},
            id=f"tu_{call_count}",
        )
        return _model_response([write])

    client.messages.create.side_effect = make_response
    docker.exec.return_value = ("", "")

    with pytest.raises(StallDetected, match="patched"):
        gen.run()


def test_stall_model_stops_repro_fails(tmp_path: Path) -> None:
    gen, docker, client = _make_generator(tmp_path)

    read_call = _tool_use_block("read_file", {"path": "src/module.py"})
    client.messages.create.side_effect = [
        _model_response([read_call]),
        _model_response([_text_block()], "end_turn"),
    ]
    docker.exec.side_effect = [
        ("code", ""),
        CommandError("pytest ...", 1, "", "FAILED"),  # repro fails
    ]

    with pytest.raises(StallDetected, match="repro command still fails"):
        gen.run()


def test_write_file_blocked_for_tests_dir(tmp_path: Path) -> None:
    gen, docker, client = _make_generator(tmp_path)

    write_tests = _tool_use_block("write_file", {"path": "tests/test_foo.py", "content": "x"})
    text_done = _text_block()
    client.messages.create.side_effect = [
        _model_response([write_tests]),
        _model_response([text_done], "end_turn"),
    ]
    # docker.exec only called for repro check (which passes)
    docker.exec.return_value = ("", "")

    gen.run()

    # Blocked write never sent to Docker; only repro check exec called
    assert docker.exec.call_count == 1
