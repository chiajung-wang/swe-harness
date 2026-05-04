# Prompt Caching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make prompt caching actually fire. Live run trace shows `cache_read_tokens: 0` on all 7 calls despite `_build_cache_block()` existing. Root cause: system prompt is ~80 tokens — below Haiku's minimum cacheable threshold. Fix: move `cache_control` from the system prompt to the initial user message (which contains `error_output` + fix contract data and grows large enough to cache). Also add `cache_creation_tokens` to `TraceEntry` so caching is observable, and account for cache-write cost in `_cost_usd()`.

**Decisions:**
- No `betas=["prompt-caching-2024-07-31"]` — Claude 4.x models support caching via standard API; `cache_control` blocks alone are sufficient.
- Cache the initial user message, not the system prompt (~80 tokens, will never reach threshold).
- Keep `_build_cache_block()` helper in `base.py` but stop calling it on the system prompt in `generator.py`.
- `cache_creation` extracted independently in `_call()` (for cost) and `entry_from_usage()` (for trace) — same pattern as `cache_read`.

**Architecture:**
1. `generator.py:run()` — remove `_build_cache_block()` from system; wrap initial user message content with `cache_control`
2. `models.py:TraceEntry` — add `cache_creation_tokens: int = 0`
3. `tracer.py:entry_from_usage()` — map `usage.cache_creation_input_tokens` → `cache_creation_tokens`
4. `base.py:_call()` — extract `cache_creation` from `usage`; pass to `_cost_usd()`
5. `base.py:_PRICING` / `_cost_usd()` — add cache-write price column (1.25× input); charge `cache_creation_tokens` at write rate

**Tech Stack:** Anthropic SDK (`usage.cache_creation_input_tokens`), Pydantic v2, existing `TraceEntry`.

---

### Task 1: Cache initial user message + surface cache_creation_tokens

**Files:**
- Modify: `src/swe_harness/agents/base.py`
- Modify: `src/swe_harness/agents/generator.py`
- Modify: `src/swe_harness/models.py`
- Modify: `src/swe_harness/tracer.py`
- Modify: `tests/test_agent_base.py`
- Modify: `tests/test_generator_agent.py`

- [ ] **Step 1: Write failing test — cache_creation_tokens logged in trace**

Update `_mock_response` helper in `tests/test_agent_base.py` to accept `cache_creation` param and add test:

```python
def _mock_response(
    input_tokens: int = 100,
    output_tokens: int = 50,
    cache_read: int | None = None,
    cache_creation: int | None = None,
) -> MagicMock:
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.cache_read_input_tokens = cache_read
    usage.cache_creation_input_tokens = cache_creation
    msg = MagicMock()
    msg.usage = usage
    return msg


def test_call_logs_cache_creation_tokens(tmp_path: Path) -> None:
    agent = _make_agent(tmp_path)
    agent._client = MagicMock()
    agent._client.messages.create.return_value = _mock_response(100, 50, cache_creation=800)

    agent._call(system="s", messages=[])

    entry = TraceEntry.model_validate_json(
        (tmp_path / "run" / "trace.ndjson").read_text(encoding="utf-8").strip()
    )
    assert entry.cache_creation_tokens == 800
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/test_agent_base.py::test_call_logs_cache_creation_tokens -v
```

Expected: `FAILED`.

- [ ] **Step 3: Write failing test — initial user message has cache_control**

Add to `tests/test_generator_agent.py`:

```python
def test_initial_user_message_has_cache_control(tmp_path: Path) -> None:
    agent = _make_generator(tmp_path)
    agent._client = MagicMock()
    # Return a stop response so the loop exits cleanly
    agent._client.messages.create.return_value = _stop_response()
    agent._docker = MagicMock()
    agent._docker.exec.return_value = ("", "")  # repro passes

    agent.run()

    _, kwargs = agent._client.messages.create.call_args_list[0]
    messages = kwargs["messages"]
    first_user = messages[0]
    assert first_user["role"] == "user"
    content = first_user["content"]
    assert isinstance(content, list)
    assert any(
        block.get("cache_control") == {"type": "ephemeral"}
        for block in content
    )
```

(Use existing `_make_generator` / `_stop_response` helpers already in `test_generator_agent.py`.)

- [ ] **Step 4: Run both new tests to verify both fail**

```
uv run pytest tests/test_agent_base.py::test_call_logs_cache_creation_tokens tests/test_generator_agent.py::test_initial_user_message_has_cache_control -v
```

Expected: both `FAILED`.

- [ ] **Step 5: Add cache_creation_tokens to TraceEntry**

In `src/swe_harness/models.py`, add field after `cache_read_tokens`:

```python
cache_creation_tokens: int = 0
```

- [ ] **Step 6: Update entry_from_usage() in tracer.py**

Change `entry_from_usage()` to capture `cache_creation_input_tokens`:

```python
cache_creation: int = (
    usage.cache_creation_input_tokens
    if usage.cache_creation_input_tokens is not None
    else 0
)
return TraceEntry(
    ...
    cache_read_tokens=cache_read,
    cache_creation_tokens=cache_creation,
    ...
)
```

- [ ] **Step 7: Update _PRICING and _cost_usd() in base.py**

Expand `_PRICING` tuple to `(input, output, cache_read, cache_write)` where `cache_write = 1.25 × input`:

```python
_PRICING: dict[str, tuple[float, float, float, float]] = {
    "claude-sonnet-4-6":         (3.0,  15.0, 0.30,  3.75),
    "claude-haiku-4-5-20251001": (0.80,  4.0, 0.08,  1.00),
    "claude-opus-4-7":           (15.0, 75.0, 1.50, 18.75),
}
```

Update `_cost_usd()`:

```python
def _cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read: int,
    cache_creation: int,
) -> float:
    p = _PRICING.get(model, _PRICING["claude-sonnet-4-6"])
    return (
        input_tokens * p[0]
        + output_tokens * p[1]
        + cache_read * p[2]
        + cache_creation * p[3]
    ) / 1_000_000
```

In `_call()`, extract `cache_creation` alongside `cache_read` and pass to `_cost_usd()`:

```python
cache_read = (
    usage.cache_read_input_tokens if usage.cache_read_input_tokens is not None else 0
)
cache_creation = (
    usage.cache_creation_input_tokens if usage.cache_creation_input_tokens is not None else 0
)
cost = _cost_usd(self._model, usage.input_tokens, usage.output_tokens, cache_read, cache_creation)
```

- [ ] **Step 8: Update generator.py — move cache_control to initial user message**

In `generator.py:run()`, change:

```python
# Before
system = [self._build_cache_block(self._build_system_prompt())]
messages: list[MessageParam] = [
    {"role": "user", "content": self._build_initial_message()}
]
```

To:

```python
# After
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
```

Also add `TextBlockParam` to the import line at the top of `generator.py`:

```python
from anthropic.types import MessageParam, TextBlockParam, ToolResultBlockParam, ToolUseBlock, ToolUnionParam
```

- [ ] **Step 9: Run both new tests — verify both pass**

```
uv run pytest tests/test_agent_base.py::test_call_logs_cache_creation_tokens tests/test_generator_agent.py::test_initial_user_message_has_cache_control -v
```

Expected: both `PASSED`.

- [ ] **Step 10: Run full test suite**

```
uv run pytest
```

Expected: all green. Fix any regressions (existing `test_call_charges_budget` checks cost math — update if needed).

- [ ] **Step 11: Commit**

```bash
git add src/swe_harness/agents/base.py src/swe_harness/agents/generator.py src/swe_harness/models.py src/swe_harness/tracer.py tests/test_agent_base.py tests/test_generator_agent.py
git commit -m "feat(caching): cache initial user message and track cache_creation_tokens"
```
