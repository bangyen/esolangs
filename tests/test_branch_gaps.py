"""Branch arms the line-coverage tests reached only one way."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.a_painter_ant import _Machine as _AntMachine
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.packlang import _Parser
from esolangs.interpreters.stack_based.three_x import run as three_x_run
from tests.interpreters.runner import run_program


class TestPainterAntDumpsOnce:
    def test_stepping_an_interrupted_machine_again_does_not_redump(self) -> None:
        """The picture is printed once, however often the machine is stepped."""
        io = ScriptedIO()
        machine = _AntMachine("Pn", io)
        machine.interrupt()
        machine.step()
        first = io.getvalue()
        assert first
        machine.step()
        machine.step()
        assert io.getvalue() == first


class TestThreeXUnmatchedOpen:
    def test_a_zero_test_with_no_matching_close_falls_through(self) -> None:
        """``(`` over a zero jumps to its ``)``, or advances when there is none."""
        with pytest.raises(HaltError, match="empty stack"):
            run_program(three_x_run, "1(", "")


class TestPacklangDeclarationScan:
    def test_a_type_followed_by_a_non_name_is_not_a_declaration(self) -> None:
        """The name check fails, so the semicolon is never looked for."""
        assert _Parser(["Integer", "5", ";"]).is_declaration() is False
