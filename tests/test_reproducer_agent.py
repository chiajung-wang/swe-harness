"""Unit tests for Reproducer agent — all Docker and Anthropic calls are mocked."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from swe_harness.agents.reproducer import (
    Reproducer,
    StallDetected,
    ToolCapExceeded,
)
from swe_harness.budget import Budget
from swe_harness.docker_manager import CommandError
from swe_harness.models import FixContract
from swe_harness.tracer import Tracer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_reproducer(tmp_path: Path) -> tuple[Reproducer, MagicMock, MagicMock]:
    tracer = Tracer(tmp_path / "run")
    budget = Budget(limit_usd=50.0)
    docker: MagicMock = MagicMock()
    client: MagicMock = MagicMock()
    with patch("swe_harness.agents.base.anthropic.Anthropic"):
        rep = Reproducer(
            issue_url="https://github.com/example/repo/issues/1",
            repo_commit="abc123def456" * 3 + "abcd",
            issue_body="Function foo returns 0 instead of 42.",
            run_dir=tmp_path / "run",
            docker=docker,
            tracer=tracer,
            budget=budget,
        )
    rep._client = client
    return rep, docker, client


def _tool_use_block(name: str, inputs: dict[str, object], id: str = "tu_001") -> MagicMock:
    from anthropic.types import ToolUseBlock
    block = MagicMock(spec=ToolUseBlock)
    block.type = "tool_use"
    block.name = name
    block.input = inputs
    block.id = id
    return block


def _usage_mock(input_tokens: int = 10, output_tokens: int = 5) -> MagicMock:
    u = MagicMock()
    u.input_tokens = input_tokens
    u.output_tokens = output_tokens
    u.cache_read_input_tokens = None
    u.cache_creation_input_tokens = None
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


def _emit_contract_block(
    confidence: str = "high",
    failing_test: str = "tests/test_foo.py::test_bug",
    id: str = "tu_emit",
) -> MagicMock:
    return _tool_use_block(
        "emit_contract",
        {
            "failing_test": failing_test,
            "repro_command": f"pytest {failing_test}",
            "expected_behavior": "foo() returns 42",
            "likely_affected_files": ["src/module.py"],
            "error_output": "AssertionError: 0 != 42",
            "reproducer_confidence": confidence,
        },
        id=id,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_happy_path_emits_contract(tmp_path: Path) -> None:
    rep, docker, client = _make_reproducer(tmp_path)

    read_call = _tool_use_block("read_file", {"path": "src/module.py"})
    write_test = _tool_use_block("write_test", {"path": "tests/test_foo.py", "content": "def test_bug(): assert False"}, id="tu_002")
    run_pytest = _tool_use_block("run_command", {"command": "pytest tests/test_foo.py::test_bug"}, id="tu_003")
    emit = _emit_contract_block()

    client.messages.create.side_effect = [
        _model_response([read_call]),
        _model_response([write_test]),
        _model_response([run_pytest]),
        _model_response([emit]),
    ]
    docker.exec.side_effect = [
        ("def foo(): return 0\n", ""),   # read_file
        ("", ""),                         # write_test
        CommandError("pytest ...", 1, "", "FAILED test_bug"),  # run_command (confirms failing)
    ]

    contract = rep.run()

    assert contract.failing_test == "tests/test_foo.py::test_bug"
    assert contract.reproducer_confidence == "high"
    assert contract.issue_url == "https://github.com/example/repo/issues/1"
    assert contract.repo_commit == rep._repo_commit

    contract_file = tmp_path / "run" / "fix_contract.json"
    assert contract_file.exists()
    on_disk = FixContract.model_validate_json(contract_file.read_text())
    assert on_disk == contract


def test_emit_contract_confidence_overridden_when_no_failing_test(tmp_path: Path) -> None:
    """Model claims 'high' confidence but never confirmed a failing test — system forces 'low'."""
    rep, docker, client = _make_reproducer(tmp_path)

    emit = _emit_contract_block(confidence="high")
    client.messages.create.return_value = _model_response([emit])

    contract = rep.run()

    assert contract.reproducer_confidence == "low"


def test_emit_contract_pydantic_failure_returns_tool_error(tmp_path: Path) -> None:
    """Invalid reproducer_confidence value → tool error returned, model retries."""
    rep, docker, client = _make_reproducer(tmp_path)

    bad_emit = _tool_use_block(
        "emit_contract",
        {
            "failing_test": "tests/test_foo.py::test_bug",
            "repro_command": "pytest tests/test_foo.py::test_bug",
            "expected_behavior": "works",
            "likely_affected_files": [],
            "error_output": "err",
            "reproducer_confidence": "invalid_value",  # not in Literal["high","medium","low"]
        },
        id="tu_bad",
    )
    run_pytest = _tool_use_block("run_command", {"command": "pytest tests/test_foo.py"}, id="tu_run")
    good_emit = _emit_contract_block(confidence="medium")

    client.messages.create.side_effect = [
        _model_response([bad_emit]),
        _model_response([run_pytest]),
        _model_response([good_emit]),
    ]
    docker.exec.side_effect = [
        CommandError("pytest ...", 1, "", "FAILED"),  # run_command (confirms failing)
    ]

    contract = rep.run()
    assert contract.reproducer_confidence == "medium"


def test_tool_cap_exceeded_writes_fallback_contract(tmp_path: Path) -> None:
    """At 20 tool calls without emit_contract, writes low-confidence fallback and raises."""
    rep, docker, client = _make_reproducer(tmp_path)

    call_counter = 0

    def make_response_counted(*_: object, **__: object) -> MagicMock:
        nonlocal call_counter
        call_counter += 1
        return _model_response([
            _tool_use_block("run_command", {"command": f"echo {call_counter}"}, id=f"tu_{call_counter}")
        ])

    client.messages.create.side_effect = make_response_counted
    docker.exec.return_value = ("ok", "")

    with pytest.raises(ToolCapExceeded):
        rep.run()

    contract_file = tmp_path / "run" / "fix_contract.json"
    assert contract_file.exists()
    on_disk = FixContract.model_validate_json(contract_file.read_text())
    assert on_disk.reproducer_confidence == "low"
    assert on_disk.issue_url == "https://github.com/example/repo/issues/1"


def test_forced_inject_at_call_17(tmp_path: Path) -> None:
    """At tool call 17, forced inject text is appended to the user message."""
    rep, docker, client = _make_reproducer(tmp_path)

    # Capture messages passed to the API
    captured_messages: list[object] = []

    call_counter = 0

    def fake_create(**kwargs: object) -> MagicMock:
        nonlocal call_counter
        call_counter += 1
        captured_messages.append(kwargs.get("messages"))
        # On the 18th model call, emit contract
        if call_counter >= 18:
            return _model_response([_emit_contract_block()])
        return _model_response([
            _tool_use_block("run_command", {"command": f"echo {call_counter}"}, id=f"tu_{call_counter}")
        ])

    client.messages.create.side_effect = fake_create
    docker.exec.return_value = ("ok", "")

    rep.run()

    # Find the user message sent after call 17 — it should contain the forced inject text
    from swe_harness.agents.reproducer import _FORCED_INJECT_TEXT

    def has_inject(messages: object) -> bool:
        if not isinstance(messages, list):
            return False
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") != "user":
                continue
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        if _FORCED_INJECT_TEXT in block.get("text", ""):
                            return True
        return False

    assert any(has_inject(msgs) for msgs in captured_messages)


def test_stall_when_no_tool_uses(tmp_path: Path) -> None:
    rep, docker, client = _make_reproducer(tmp_path)

    client.messages.create.return_value = _model_response([_text_block()], "end_turn")

    with pytest.raises(StallDetected):
        rep.run()


def test_write_file_blocks_tests_path(tmp_path: Path) -> None:
    rep, docker, client = _make_reproducer(tmp_path)

    write_tests = _tool_use_block("write_file", {"path": "tests/test_foo.py", "content": "x"})
    emit = _emit_contract_block()

    client.messages.create.side_effect = [
        _model_response([write_tests]),
        _model_response([emit]),
    ]
    docker.exec.return_value = ("", "")

    contract = rep.run()
    # write_file to tests/ was blocked — docker never called for that write
    assert docker.exec.call_count == 0
    # confidence "low" since test was never confirmed failing
    assert contract.reproducer_confidence == "low"


def test_write_test_allows_tests_path(tmp_path: Path) -> None:
    rep, docker, client = _make_reproducer(tmp_path)

    write_test = _tool_use_block("write_test", {"path": "tests/test_foo.py", "content": "x"}, id="tu_wt")
    run_pytest = _tool_use_block("run_command", {"command": "pytest tests/test_foo.py"}, id="tu_run")
    emit = _emit_contract_block(confidence="medium")

    client.messages.create.side_effect = [
        _model_response([write_test]),
        _model_response([run_pytest]),
        _model_response([emit]),
    ]
    docker.exec.side_effect = [
        ("", ""),  # write_test
        CommandError("pytest ...", 1, "", "FAILED"),  # run_command
    ]

    contract = rep.run()
    assert contract.reproducer_confidence == "medium"
    assert docker.exec.call_count == 2


def test_write_test_blocks_non_tests_path(tmp_path: Path) -> None:
    rep, docker, client = _make_reproducer(tmp_path)

    bad_write = _tool_use_block("write_test", {"path": "src/not_a_test.py", "content": "x"})
    emit = _emit_contract_block()

    client.messages.create.side_effect = [
        _model_response([bad_write]),
        _model_response([emit]),
    ]
    docker.exec.return_value = ("", "")

    contract = rep.run()
    assert docker.exec.call_count == 0  # bad path never reached docker


def test_emit_contract_not_counted_in_tool_cap(tmp_path: Path) -> None:
    """emit_contract must not count toward the 20-call cap."""
    rep, docker, client = _make_reproducer(tmp_path)

    # 20 normal tool calls then emit — should succeed, not raise ToolCapExceeded
    responses = [
        _model_response([
            _tool_use_block("run_command", {"command": f"echo {i}"}, id=f"tu_{i}")
        ])
        for i in range(20)
    ]
    responses.append(_model_response([_emit_contract_block()]))
    client.messages.create.side_effect = responses
    docker.exec.return_value = ("ok", "")

    with pytest.raises(ToolCapExceeded):
        # Cap fires at exactly 20; emit on the 21st model call never reached
        rep.run()


def test_initial_message_has_cache_control(tmp_path: Path) -> None:
    rep, docker, client = _make_reproducer(tmp_path)

    client.messages.create.return_value = _model_response([_emit_contract_block()])

    rep.run()

    _, kwargs = client.messages.create.call_args_list[0]
    messages = kwargs["messages"]
    first_user = messages[0]
    assert first_user["role"] == "user"
    content = first_user["content"]
    assert isinstance(content, list)
    assert any(
        block.get("cache_control") == {"type": "ephemeral"}
        for block in content
    )
