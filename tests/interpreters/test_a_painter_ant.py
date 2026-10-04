"""Malformed-program diagnostics and the shared empty-program contract."""

import pytest

from esolangs.interpreters.grid_based.a_painter_ant import run
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.contract import EmptyProgramContract


def run_program(code: str) -> str:
    io = ScriptedIO()
    run(code, io)
    return io.getvalue()


class TestFormat:
    def test_unknown_instruction_is_malformed(self) -> None:
        with pytest.raises(ValueError, match="unknown instruction"):
            run_program("Px")


class TestContract(EmptyProgramContract):
    run = staticmethod(run_program)
    empty_output = "o"
