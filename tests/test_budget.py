import logging

import pytest

from swe_harness.budget import Budget, BudgetExceeded


def test_normal_accumulation() -> None:
    b = Budget(limit_usd=200.0)
    b.charge(10.0)
    b.charge(5.0)
    assert b.spent == pytest.approx(15.0)


def test_warn_at_50(caplog: pytest.LogCaptureFixture) -> None:
    b = Budget(limit_usd=200.0)
    with caplog.at_level(logging.WARNING, logger="swe_harness.budget"):
        b.charge(50.0)
    assert any("threshold: $50" in m for m in caplog.messages)


def test_warn_at_100(caplog: pytest.LogCaptureFixture) -> None:
    b = Budget(limit_usd=200.0)
    with caplog.at_level(logging.WARNING, logger="swe_harness.budget"):
        b.charge(100.0)
    messages = caplog.messages
    assert any("threshold: $50" in m for m in messages)
    assert any("threshold: $100" in m for m in messages)


def test_warn_at_150(caplog: pytest.LogCaptureFixture) -> None:
    b = Budget(limit_usd=200.0)
    with caplog.at_level(logging.WARNING, logger="swe_harness.budget"):
        b.charge(150.0)
    messages = caplog.messages
    assert any("threshold: $50" in m for m in messages)
    assert any("threshold: $100" in m for m in messages)
    assert any("threshold: $150" in m for m in messages)


def test_warn_fires_once_per_threshold(caplog: pytest.LogCaptureFixture) -> None:
    b = Budget(limit_usd=200.0)
    with caplog.at_level(logging.WARNING, logger="swe_harness.budget"):
        b.charge(50.0)
        b.charge(1.0)
    assert sum(1 for m in caplog.messages if "threshold: $50" in m) == 1


def test_hard_kill_at_limit() -> None:
    b = Budget(limit_usd=200.0)
    with pytest.raises(BudgetExceeded) as exc_info:
        b.charge(200.01)
    err = exc_info.value
    assert err.spent == pytest.approx(200.01)
    assert err.limit == pytest.approx(200.0)


def test_budget_exceeded_carries_fields() -> None:
    b = Budget(limit_usd=100.0)
    with pytest.raises(BudgetExceeded) as exc_info:
        b.charge(101.0)
    assert exc_info.value.spent == pytest.approx(101.0)
    assert exc_info.value.limit == pytest.approx(100.0)


def test_spent_updated_before_raise() -> None:
    b = Budget(limit_usd=10.0)
    with pytest.raises(BudgetExceeded):
        b.charge(11.0)
    assert b.spent == pytest.approx(11.0)


def test_charge_raises_budget_exceeded() -> None:
    b = Budget(limit_usd=1.0)
    with pytest.raises(BudgetExceeded):
        b.charge(1.0)  # spend == limit should raise


def test_charge_rejects_negative_cost() -> None:
    b = Budget(limit_usd=200.0)
    with pytest.raises(ValueError):
        b.charge(-1.0)
