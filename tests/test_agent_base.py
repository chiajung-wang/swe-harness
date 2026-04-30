from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from swe_harness.agents.base import AnthropicAgent
from swe_harness.budget import Budget, BudgetExceeded
from swe_harness.models import TraceEntry
from swe_harness.tracer import Tracer


def _mock_response(input_tokens: int = 100, output_tokens: int = 50, cache_read: int | None = None) -> MagicMock:
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.cache_read_input_tokens = cache_read
    msg = MagicMock()
    msg.usage = usage
    return msg


def _make_agent(tmp_path: Path, *, limit_usd: float = 10.0) -> AnthropicAgent:
    tracer = Tracer(tmp_path / "run")
    budget = Budget(limit_usd=limit_usd)
    with patch("swe_harness.agents.base.anthropic.Anthropic"):
        agent = AnthropicAgent(
            model="claude-sonnet-4-6",
            run_id="test-run-001",
            tracer=tracer,
            budget=budget,
        )
    return agent


def test_call_logs_trace_entry(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    agent._client = MagicMock()
    agent._client.messages.create.return_value = _mock_response(100, 50)

    agent._call(system="Be helpful.", messages=[])

    lines = (tmp_path / "run" / "trace.ndjson").read_text(encoding="utf-8").strip().split("\n")
    assert len(lines) == 1
    entry = TraceEntry.model_validate_json(lines[0])
    assert entry.run_id == "test-run-001"
    assert entry.agent == "AnthropicAgent"
    assert entry.model == "claude-sonnet-4-6"
    assert entry.event == "model_call"
    assert entry.input_tokens == 100
    assert entry.output_tokens == 50
    assert entry.cost_usd > 0


def test_call_charges_budget(tmp_path: Path) -> None:
    tracer = Tracer(tmp_path / "run")
    budget = Budget(limit_usd=10.0)
    with patch("swe_harness.agents.base.anthropic.Anthropic"):
        agent = AnthropicAgent(model="claude-sonnet-4-6", run_id="r", tracer=tracer, budget=budget)
    agent._client = MagicMock()
    agent._client.messages.create.return_value = _mock_response(1_000_000, 0)

    agent._call(system="s", messages=[])

    # 1M input tokens at $3/MTok = $3.00
    assert abs(budget.spent - 3.0) < 0.01


def test_call_propagates_api_error(tmp_path: Path) -> None:
    import anthropic as sdk

    agent = _make_agent(tmp_path)
    agent._client = MagicMock()
    agent._client.messages.create.side_effect = sdk.APIConnectionError(request=MagicMock())

    with pytest.raises(sdk.APIConnectionError):
        agent._call(system="s", messages=[])

    # API error fires before tracer.log — trace file must remain empty
    assert (tmp_path / "run" / "trace.ndjson").read_text(encoding="utf-8") == ""


def test_call_propagates_budget_exceeded(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path, limit_usd=0.000001)
    agent._client = MagicMock()
    agent._client.messages.create.return_value = _mock_response(1, 1)

    with pytest.raises(BudgetExceeded):
        agent._call(system="s", messages=[])


def test_call_cache_read_none_treated_as_zero(tmp_path: Path) -> None:
    # SDK may return None for cache_read_input_tokens on non-cached calls
    agent = _make_agent(tmp_path)
    agent._client = MagicMock()
    agent._client.messages.create.return_value = _mock_response(100, 50, cache_read=None)

    agent._call(system="s", messages=[])

    entry = TraceEntry.model_validate_json(
        (tmp_path / "run" / "trace.ndjson").read_text(encoding="utf-8").strip()
    )
    assert entry.cache_read_tokens == 0


def test_build_cache_block(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    block = agent._build_cache_block("system prompt text")
    assert block["type"] == "text"
    assert block["text"] == "system prompt text"
    assert block["cache_control"] == {"type": "ephemeral"}
