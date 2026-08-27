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
        # t=3: the cross-check reserves a cell for variable-variable arithmetic
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


class TestMalformedStatements:
    """Each part of a statement's shape is checked, not just its first token.

    The parser walks ``if``/``while`` and ``write``/``read`` piece by piece,
    giving up at the first part that does not fit.  Every one of those
    give-up points rejected the same way, so a program that got a later part
    wrong was accepted or rejected by whichever check happened to run --
    these pin one malformed program per part.  Each carries trailing
    statements so the ``ind + 4 < size`` lookahead is satisfied and the
    parse really does reach the part under test.
    """

    TAIL = "\na += 1;\na += 1;\na += 1;\n"

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param("while a ) { }", id="no-open-paren"),
            pytest.param("while ( 5 ) { }", id="condition-not-a-name"),
            pytest.param("while ( a a { }", id="no-closing-paren"),
            pytest.param("while ( a ) a", id="no-opening-brace"),
        ],
    )
    def test_a_malformed_loop_header_is_rejected(self, body: str) -> None:
        with pytest.raises(ValueError, match="Invalid syntax"):
            run_program(H + body + self.TAIL)

    @pytest.mark.parametrize(
        "body",
        [
            pytest.param("write -> a ;", id="write-takes-left-arrow"),
            pytest.param("write <- 5 ;", id="target-not-a-name"),
            pytest.param("write <- a a", id="no-semicolon"),
            pytest.param("read <- a ;", id="read-takes-right-arrow"),
        ],
    )
    def test_a_malformed_io_statement_is_rejected(self, body: str) -> None:
        with pytest.raises(ValueError, match="Invalid syntax"):
            run_program(H + body + self.TAIL)


class TestNestedBlocks:
    def test_a_block_inside_a_loop_body_is_matched_to_its_own_close(self) -> None:
        """Finding a loop's end counts nesting rather than taking the first ``}``.

        The scan walks the compiled program keeping a depth counter, so an
        inner block's close belongs to the inner block.  Without the count
        the outer loop would end early, at the ``if``'s brace, and run only
        part of its body.
        """
        header = "#basicfuck t=4 r=0~255 o=nearest\n#allocate a b\n"
        program = (
            "a += 2;\n"
            "while ( a ) {\n"
            "  b += 1;\n"
            "  if ( b ) {\n"
            "    b -= 1;\n"
            "  }\n"
            "  a -= 1;\n"
            "}\n"
            "a += 65;\n"
            "write <- a ;"
        )
        # The loop runs to completion (a reaches 0) before the 65 is added.
        assert run_program(header + program) == "A"


class TestStepMachine:
    def test_step_tracks_tape_and_cursor(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.basicfuck import _Machine

        prog = "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\n"
        machine = _Machine(prog + "a += 65;\nwrite <- a ;", ScriptedIO())
        assert (machine.frames[-1].ptr, list(machine.tape.cells())) == (0, [0])
        machine.step()  # a += 65
        assert list(machine.tape.cells()) == [65]
        machine.step()  # write prints a
        assert machine.io.getvalue() == "A"
        machine.step()  # the finished frame is finalized
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.frames == []

    def test_snapshot_is_hashable(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.basicfuck import _Machine

        prog = "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\n"
        assert hash(_Machine(prog, ScriptedIO()).snapshot()) is not None

    def test_halting_program_is_detected(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.basicfuck import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        prog = "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\n"
        assert run_until_halt_or_cycle(_Machine(prog + "a += 1;", ScriptedIO())) is True

    def test_while_loop_is_detected_as_a_cycle(self) -> None:
        """A while loop whose body never changes its condition loops forever."""
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.basicfuck import _Machine
        from esolangs.vm import run_until_halt_or_cycle

        prog = "#basicfuck t=1 r=0~255 o=wrap\n#allocate a\n"
        code = prog + "a += 1;\nwhile (a) { }"
        assert run_until_halt_or_cycle(_Machine(code, ScriptedIO())) is False
