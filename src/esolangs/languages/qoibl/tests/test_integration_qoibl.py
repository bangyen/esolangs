"""Qoibl through the shared API, CLI and machinery."""

import pytest

import esolangs
import esolangs.runtime._execution as _execution_runtime
from esolangs import run
from tests.support.generator_support import verify_generated
from tests.support.reference import REFERENCE


@pytest.mark.medium
@pytest.mark.parametrize(
    ("value", "stdin", "error_type", "message", "past_end", "replay"),
    [
        ("et", "", esolangs.InputExhaustedError, "past the end", 1, ()),
        (
            "et ry yy ry e",
            "Q",
            esolangs.HaltError,
            "81 divided by 0",
            0,
            (ord("Q"),),
        ),
    ],
)
def test_failed_statements_preserve_evidence_on_retry(
    value, stdin, error_type, message, past_end, replay
) -> None:
    api = esolangs.Language("Qoibl")
    source = f"we tt yeeeeey tt we {value} we"
    consumed = len(stdin)
    for outcome in (
        api.execute(source, stdin=stdin),
        api.prepare(source).execute(stdin=stdin),
        api.execute(source, stdin=stdin, isolated=True),
    ):
        assert type(outcome.error) is error_type
        assert message in str(outcome.error)
        assert outcome.observation == esolangs.ExecutionResult(
            "A", consumed, consumed, past_end
        )

    debugger = api.make_debugger(source, stdin=stdin)
    fault_state = None
    for attempt in (1, 2):
        with pytest.raises(error_type, match=message) as caught:
            debugger.step()
        assert debugger.ip == 0
        assert caught.value.observation == esolangs.ExecutionResult(
            "A", consumed, consumed, attempt * past_end, steps=0
        )
        snapshot = debugger.snapshot()
        assert snapshot[-1] == (replay, 1)
        if fault_state is not None:
            assert snapshot == fault_state
        fault_state = snapshot


class TestAnInterpreterLimitIsStillAnEsolangError:
    """Qoibl's interpreter recurses, and Python's stack is finite."""

    @staticmethod
    def _parity(n: int) -> str:
        """Return the parity table of arity ``n`` -- reliably a hard one."""
        return "".join(str((i).bit_count() % 2) for i in range(2**n))

    def test_a_recursion_error_does_not_escape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """It was the one exception in the package that was not ours."""

        def explode(*_args: object, **_kwargs: object) -> None:
            raise RecursionError("maximum recursion depth exceeded")

        monkeypatch.setattr(_execution_runtime, "invoke", explode)
        with pytest.raises(esolangs.EsolangError) as caught:
            run(REFERENCE, "+.", stdin="")
        assert isinstance(caught.value, esolangs.InterpreterLimitError)
        assert "recursed deeper" in str(caught.value)
        assert "setrecursionlimit" in str(caught.value)

    def test_a_memory_error_does_not_escape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In-process allocation failures must reach the API as interpreter limits."""

        def explode(*_args: object, **_kwargs: object) -> None:
            raise MemoryError

        monkeypatch.setattr(_execution_runtime, "invoke", explode)
        with pytest.raises(esolangs.InterpreterLimitError, match="out of memory"):
            run(REFERENCE, "+.", stdin="")

    @pytest.mark.slow
    def test_qoibl_no_longer_hits_the_wall(self) -> None:
        """The six-input table this class was built around now computes."""
        assert verify_generated("Qoibl", self._parity(6), timeout=300)
