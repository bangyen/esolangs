"""Explicit execution and whole-invocation budgets."""

from dataclasses import dataclass

from esolangs.exceptions import ArgumentError
from esolangs.runtime._validate import check_timeout, check_whole


@dataclass(frozen=True, slots=True)
class ExecutionLimits:
    """Preparation, execution and whole-invocation budgets.

    A preparation deadline covers acquisition, worker startup and the source
    preparation hook. It selects isolation when source needs preparing.
    Execution deadlines select isolation even with a step limit. Total, output
    and memory limits also select isolation. Memory limits require Linux. An
    isolated invocation without total_timeout gets 30 seconds plus any
    execution_timeout.  ``run(timeout=t)`` is ``execution_timeout=t``.
    """

    execution_timeout: float | None = None
    total_timeout: float | None = None
    max_steps: int | None = None
    max_output: int | None = None
    max_memory: int | None = None
    preparation_timeout: float | None = None

    def __post_init__(self) -> None:
        """Refuse invalid budgets before acquiring source or input."""
        check_timeout(self.preparation_timeout, "preparation_timeout")
        check_timeout(self.execution_timeout, "execution_timeout")
        check_timeout(self.total_timeout, "total_timeout")
        for name in ("max_steps", "max_output"):
            value = getattr(self, name)
            if value is not None:
                check_whole(value, name)
        memory = self.max_memory
        if memory is not None and (
            isinstance(memory, bool) or not isinstance(memory, int) or memory <= 0
        ):
            raise ArgumentError(
                f"max_memory must be a positive integer, got {memory!r}"
            )
