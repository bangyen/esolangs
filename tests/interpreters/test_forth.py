"""Unit tests for the Forþ interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.forth import run
from tests.interpreters.contract import (
    CycleContract,
    EmptyProgramContract,
    InputCursorContract,
)


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class TestForth:
    def test_empty_stack_pop_halts(self) -> None:
        with pytest.raises(HaltError):
            run_program(".")

    def test_binary_underflow_halts(self) -> None:
        with pytest.raises(HaltError):
            run_program("9/")

    def test_rotate_underflow_halts(self) -> None:
        with pytest.raises(HaltError):
            run_program("12c")

    def test_division_by_zero_halts(self) -> None:
        with pytest.raises(HaltError):
            run_program("50/")
        with pytest.raises(HaltError):
            run_program("50%")

    def test_unterminated_bracket_halts(self) -> None:
        with pytest.raises(HaltError):
            run_program("(5")
        with pytest.raises(HaltError):
            run_program("[")

    def test_nested_empty_pop_is_fatal(self) -> None:
        """An empty-stack pop inside a called scope halts the whole program."""
        with pytest.raises(HaltError):
            run_program("1{.};")


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.forth import _Machine

    return _Machine(code, ScriptedIO())


def _reader(code: object, stdin: str) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.stack_based.forth import _Machine

    return _Machine(code, ScriptedIO(stdin))


class TestContract(EmptyProgramContract, CycleContract, InputCursorContract):
    """The shared empty-program shape, with this language's data."""

    run = staticmethod(run_program)
    machine = staticmethod(_machine)
    reader = staticmethod(_reader)
    reading_program = ","
    reading_stdin = "hi"
    position_after_read = 2
    halting_program = "65."
    looping_program = "1[]"
