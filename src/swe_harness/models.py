from typing import Literal

from pydantic import BaseModel


class FixContract(BaseModel):
    issue_url: str
    repo_commit: str
    failing_test: str
    repro_command: str
    expected_behavior: str
    likely_affected_files: list[str]
    error_output: str
    reproducer_confidence: Literal["high", "medium", "low"]


class SprintContract(BaseModel):
    files_to_modify: list[str]
    approach: str
    risks: str


class Verdict(BaseModel):
    run_id: str
    round: int
    verdict: Literal["pass", "fail"]
    hacks_detected: list[str]
    regressions: list[str]
    feedback: str
    suite_passed: bool
    suite_total: int
    suite_failed: int


class TraceEntry(BaseModel):
    ts: str
    run_id: str
    agent: str
    event: Literal["tool_call", "model_call", "artifact_written"]
    model: str = ""
    tool: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: int = 0


class RunRecord(BaseModel):
    run_id: str
    issue_url: str
    config: Literal["solo", "two_agent", "three_agent", "full"]
    verdict: Literal["pass", "fail"] | None
    rounds: int
    cost_usd: float
    duration_s: float
    ts: str
