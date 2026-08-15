"""Unit tests for the 3D Brainfuck interpreter."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.three_d_brainfuck import run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


class Test3DBrainfuck:
    def test_increment_and_print(self) -> None:
        assert run_program("+.") == "\x01"

    def test_cell_wraps(self) -> None:
        assert run_program("+" * 255 + ".") == "\xff"
        assert run_program("+" * 256 + ".") == "\x00"

    def test_array_moves(self) -> None:
        # n/e/u move the array pointer along the X/Z/Y axes
        assert run_program("n+.") == "\x01"
        assert run_program("ne+.") == "\x01"
        assert run_program("neu+.") == "\x01"

    def test_three_dimensional_cells_are_distinct(self) -> None:
        # n, e, u point at three distinct array cells; each + sets that cell
        assert run_program("n+.e+.u+.") == "\x01\x01\x01"

    def test_loop(self) -> None:
        assert run_program("++[-].") == "\x00"
        assert run_program("n+[-].") == "\x00"

    def test_input(self) -> None:
        assert run_program(",.", "X\n") == "X"

    def test_heading_default_is_plus_x(self) -> None:
        assert run_program("N+.") == "\x01"

    def test_heading_off_line_halts(self) -> None:
        # U sets heading +Y; the pointer walks off the source line and halts
        assert run_program("U+.") == ""

    def test_generation_blocks_are_noops(self) -> None:
        # ^/V/>/</"/' set the generation heading only
        assert run_program("^+.") == "\x01"
        assert run_program("'n+.") == "\x01"

    def test_comment_characters_are_noops(self) -> None:
        assert run_program("a+b.c") == "\x01"

    def test_malformed_brackets(self) -> None:
        with pytest.raises(ValueError, match="unmatched"):
            run_program("[")
        with pytest.raises(ValueError, match="unmatched"):
            run_program("]")

    def test_empty_program(self) -> None:
        assert run_program("") == ""
