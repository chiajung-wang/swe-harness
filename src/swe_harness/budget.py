import logging

logger = logging.getLogger(__name__)

_WARN_THRESHOLDS = (50.0, 100.0, 150.0)


class BudgetExceeded(Exception):
    def __init__(self, spent: float, limit: float) -> None:
        self.spent = spent
        self.limit = limit
        super().__init__(f"Budget exceeded: ${spent:.4f} of ${limit:.2f}")


class Budget:
    def __init__(self, limit_usd: float) -> None:
        self.limit_usd = limit_usd
        self._spent: float = 0.0
        self._warned: set[float] = set()

    @property
    def spent(self) -> float:
        return self._spent

    def charge(self, cost: float) -> None:
        if cost < 0:
            raise ValueError(f"cost must be non-negative, got {cost}")
        self._spent += cost
        for threshold in _WARN_THRESHOLDS:
            if self._spent >= threshold and threshold not in self._warned:
                self._warned.add(threshold)
                logger.warning(
                    "Budget warning: $%.4f spent (threshold: $%.0f, limit: $%.2f)",
                    self._spent,
                    threshold,
                    self.limit_usd,
                )
        if self._spent >= self.limit_usd:
            raise BudgetExceeded(spent=self._spent, limit=self.limit_usd)
