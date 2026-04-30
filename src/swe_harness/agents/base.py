from __future__ import annotations

import time

import anthropic
from anthropic.types import Message, MessageParam, TextBlockParam, ToolUnionParam

from swe_harness.budget import Budget
from swe_harness.tracer import Tracer, entry_from_usage

# Per-million-token pricing: (input, output, cache_read)
_PRICING: dict[str, tuple[float, float, float]] = {
    "claude-sonnet-4-6": (3.0, 15.0, 0.30),
    "claude-haiku-4-5-20251001": (0.80, 4.0, 0.08),
    "claude-opus-4-7": (15.0, 75.0, 1.50),
}

_DEFAULT_MAX_TOKENS = 8192


def _cost_usd(model: str, input_tokens: int, output_tokens: int, cache_read: int) -> float:
    p = _PRICING.get(model, _PRICING["claude-sonnet-4-6"])
    return (input_tokens * p[0] + output_tokens * p[1] + cache_read * p[2]) / 1_000_000


class AnthropicAgent:
    """Base class for all three agents (Reproducer, Generator, Evaluator).

    Owns the Anthropic client, prompt-cache helper, and the instrumented
    _call() that logs every model call and charges the shared budget.
    """

    def __init__(self, model: str, run_id: str, tracer: Tracer, budget: Budget) -> None:
        self._model = model
        self._run_id = run_id
        self._tracer = tracer
        self._budget = budget
        self._client = anthropic.Anthropic()

    def _build_cache_block(self, content: str) -> TextBlockParam:
        """Wrap content as an ephemeral prompt-cache text block."""
        return TextBlockParam(
            type="text",
            text=content,
            cache_control={"type": "ephemeral"},
        )

    def _call(
        self,
        system: str | list[TextBlockParam],
        messages: list[MessageParam],
        tools: list[ToolUnionParam] | None = None,
    ) -> Message:
        """Call the Anthropic API, log a TraceEntry, and charge the budget.

        API errors propagate to the caller — no swallowing.
        """
        start = time.monotonic()

        response: Message = self._client.messages.create(
            model=self._model,
            max_tokens=_DEFAULT_MAX_TOKENS,
            system=system,
            messages=messages,
            tools=tools if tools is not None else anthropic.omit,
        )

        duration_ms = int((time.monotonic() - start) * 1000)
        usage = response.usage
        cache_read = (
            usage.cache_read_input_tokens if usage.cache_read_input_tokens is not None else 0
        )
        cost = _cost_usd(self._model, usage.input_tokens, usage.output_tokens, cache_read)

        # Trace before charging: the API call completed and tokens were consumed
        # by Anthropic, so the trace entry is valid even if budget.charge()
        # raises BudgetExceeded immediately after.
        self._tracer.log(
            entry_from_usage(
                run_id=self._run_id,
                agent=type(self).__name__,
                model=self._model,
                usage=usage,
                cost_usd=cost,
                duration_ms=duration_ms,
            )
        )
        self._budget.charge(cost)

        return response
