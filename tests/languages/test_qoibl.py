"""Qoibl through the shared API, CLI and machinery."""

import pytest

import esolangs
from tests.support.generator_support import verify_generated


class TestAnInterpreterLimitIsStillAnEsolangError:
    """Qoibl's interpreter recurses, and Python's stack is finite."""

    @staticmethod
    def _parity(n: int) -> str:
        """Return the parity table of arity ``n`` -- reliably a hard one."""
        return "".join(str(bin(i).count("1") % 2) for i in range(2**n))

    def test_a_recursion_error_does_not_escape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """It was the one exception in the package that was not ours."""

        def explode(*_args: object, **_kwargs: object) -> None:
            raise RecursionError("maximum recursion depth exceeded")

        monkeypatch.setattr(esolangs, "_run", explode)
        with pytest.raises(esolangs.EsolangError) as caught:
            esolangs.run("brainfuck", "+.", stdin="")
        assert isinstance(caught.value, esolangs.InterpreterLimitError)
        assert "recursed deeper" in str(caught.value)
        assert "setrecursionlimit" in str(caught.value)

    def test_a_memory_error_does_not_escape(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In process, Underload's string doubling reached it raw."""

        def explode(*_args: object, **_kwargs: object) -> None:
            raise MemoryError

        monkeypatch.setattr(esolangs, "_run", explode)
        with pytest.raises(esolangs.InterpreterLimitError, match="out of memory"):
            esolangs.run("brainfuck", "+.", stdin="")

    @pytest.mark.slow
    def test_qoibl_no_longer_hits_the_wall(self) -> None:
        """The six-input table this class was built around now computes."""
        assert verify_generated("Qoibl", self._parity(6), timeout=300)
