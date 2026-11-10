"""Explicit execution and whole-invocation budgets."""

from dataclasses import dataclass

from esolangs.exceptions import ArgumentError
from esolangs.runtime._validate import check_timeout, check_whole


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    """Execution time excludes acquisition; total time includes worker startup.

    Total, output and memory limits select isolation. Memory limits require
    Linux. An isolated invocation without total_timeout retains the 30s default.
    Cooperative execution time cannot interrupt preparation or one command.
    """

    execution_timeout: float | None = None
    total_timeout: float | None = None
    max_steps: int | None = None
    max_output: int | None = None
    max_memory: int | None = None

    def __post_init__(self) -> None:
        """Refuse invalid budgets before acquiring source or input."""
        check_timeout(self.execution_timeout)
        check_timeout(self.total_timeout)
        for name in ("max_steps", "max_output", "max_memory"):
            value = getattr(self, name)
            if value is not None:
                check_whole(value, name)
                if name == "max_memory" and value == 0:
                    raise ArgumentError("max_memory must be positive")
