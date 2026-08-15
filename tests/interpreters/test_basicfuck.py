"""Unit tests for the Basicfuck interpreter."""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.basicfuck import run


def run_program(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


H = "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\n"


class TestBasicfuck:
    def test_write_constant(self) -> None:
        assert run_program(H + "a += 65;\nwrite <- a ;") == "A"

    def test_overflow_nearest_clamps(self) -> None:
        assert run_program(H + "a += 300;\nwrite <- a ;") == "\xff"
        assert run_program(H + "a -= 300;\nwrite <- a ;") == "\x00"

    def test_overflow_wrap(self) -> None:
        prog = "#basicfuck t=1 r=0~255 o=wrap\n#allocate a\n"
        assert run_program(prog + "a += 256;\nwrite <- a ;") == "\x00"

    def test_overflow_halt_raises(self) -> None:
        prog = "#basicfuck t=1 r=0~255 o=halt\n#allocate a\n"
        with pytest.raises(HaltError):
            run_program(prog + "a += 256;")
        with pytest.raises(HaltError):
            run_program(prog + "a -= 1;")

    def test_var_to_var(self) -> None:
        # t=3: the reference reserves a cell for variable-variable arithmetic
        prog = "#basicfuck t=3 r=0~255 o=wrap\n#allocate a, b\n"
        assert run_program(prog + "a += 5;\nb += a;\nwrite <- b ;") == "\x05"

    def test_read(self) -> None:
        prog = "#basicfuck t=unbounded r=0~255 o=wrap\n#allocate a\n"
        assert run_program(prog + "read -> a ;\nwrite <- a ;", "X\n") == "X"

    def test_read_and_normalize(self) -> None:
        prog = "#basicfuck t=unbounded r=0~255 o=wrap\n#allocate a\n"
        assert (
            run_program(prog + "read -> a ;\na -= 48 ;\nwrite <- a ;", "0\n") == "\x00"
        )

    def test_if_branch(self) -> None:
        prog = "#basicfuck t=unbounded r=0~255 o=wrap\n#allocate a\n"
        assert run_program(prog + "a += 1;\nif (a) { write <- a ; }") == "\x01"
        assert run_program(prog + "a += 0;\nif (a) { write <- a ; }") == ""

    def test_if_negated(self) -> None:
        prog = "#basicfuck t=unbounded r=0~255 o=wrap\n#allocate a\n"
        assert run_program(prog + "a += 0;\nif !(a) { write <- a ; }") == "\x00"

    def test_while_loop(self) -> None:
        prog = "#basicfuck t=unbounded r=0~255 o=wrap\n#allocate a\n"
        code = prog + "a += 5;\nwhile (a) { a -= 1; }\nwrite <- a ;"
        assert run_program(code) == "\x00"

    def test_array_indexing(self) -> None:
        prog = "#basicfuck t=unbounded r=0~255 o=wrap\n#allocate a->2\n"
        code = prog + "a->0 += 65;\nwrite <- a->0 ;\na->1 += 66;\nwrite <- a->1 ;"
        assert run_program(code) == "AB"

    def test_comments_stripped(self) -> None:
        assert run_program(H + "a += 65; // comment\nwrite <- a ;") == "A"

    def test_malformed_directive(self) -> None:
        with pytest.raises(ValueError, match="directives"):
            run_program("not a directive\n#allocate a\n")

    def test_missing_overflow_directive(self) -> None:
        with pytest.raises(ValueError, match="overflow"):
            run_program("#basicfuck t=1 r=0~255\n#allocate a\n")

    def test_malformed_allocate(self) -> None:
        with pytest.raises(ValueError, match="identifiers"):
            run_program("#basicfuck t=1 r=0~255 o=nearest\nbad alloc\n")

    def test_keyword_identifier(self) -> None:
        with pytest.raises(ValueError, match="identifier"):
            run_program("#basicfuck t=1 r=0~255 o=nearest\n#allocate write\n")

    def test_undefined_identifier(self) -> None:
        with pytest.raises(ValueError, match="undefined"):
            run_program(H + "z += 1;")

    def test_invalid_syntax(self) -> None:
        with pytest.raises(ValueError, match="syntax"):
            run_program(H + "a += ;")
        with pytest.raises(ValueError, match="syntax"):
            run_program(H + "a 5 1 ;")  # missing += / -=
        with pytest.raises(ValueError, match="syntax"):
            run_program(H + "a += {;")  # a constant that is not a number
        with pytest.raises(ValueError, match="syntax"):
            run_program(H + "write a b ;")  # missing the <- arrow
        with pytest.raises(ValueError, match="syntax"):
            run_program(H + "read a b ;")  # missing the -> arrow
        with pytest.raises(ValueError, match="syntax"):
            run_program(H + "if (a { a += 1; }")  # missing the closing )

    def test_invalid_token(self) -> None:
        with pytest.raises(ValueError, match="token"):
            run_program(H + "a += 1 @ 2;")

    def test_unbalanced_block(self) -> None:
        with pytest.raises(ValueError, match="syntax"):
            run_program(H + "if (a) { write <- a ;")

    def test_insufficient_memory(self) -> None:
        with pytest.raises(ValueError, match="memory"):
            run_program("#basicfuck t=1 r=0~255 o=nearest\n#allocate a, b\n")

    def test_invalid_overflow_directive(self) -> None:
        """A one-sided range with ``o=wrap`` is rejected."""
        with pytest.raises(ValueError, match="overflow"):
            run_program("#basicfuck t=1 r=0~ o=wrap\n#allocate a\n")

    def test_array_access_out_of_bounds_halts(self) -> None:
        """Reading or writing past an array's allocation is an invalid op."""
        ub = "#basicfuck t=unbounded r=0~255 o=nearest\n#allocate a->2\n"
        with pytest.raises(HaltError):
            run_program(ub + "write <- a->5 ;")
        with pytest.raises(HaltError):
            run_program(ub + "read -> a->5 ;", "A\n")
