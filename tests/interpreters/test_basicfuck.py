"""Unit tests for the Basicfuck interpreter."""

import re

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.basicfuck import run
from tests.interpreters.contract import CycleContract, SnapshotContract
from tests.raises import raises_message


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

    def test_every_rejection_message_is_exact(self) -> None:
        """Each load error is pinned whole, not by a fragment of itself.

        ``match=`` is a substring search, so ``"identifier"`` also matches
        ``"Missing/Invalid identifiers."`` -- the two checks above cannot
        tell each other apart, and every message was free to be reworded.
        Two more rejections had no test at all: an unrecognised overflow
        mode falls in with the malformed directives, and a zero-cell tape
        is refused for its size.
        """
        for code, message in (
            ("not a directive\n#allocate a\n", "Missing/Invalid directives."),
            (
                "#basicfuck t=1 r=0~255 o=bad\n#allocate a\n",
                "Missing/Invalid directives.",
            ),
            ("#basicfuck t=1 r=0~255\n#allocate a\n", "Missing overflow directive."),
            (
                "#basicfuck t=1 r=0~255 o=nearest\nbad alloc\n",
                "Missing/Invalid identifiers.",
            ),
            (
                "#basicfuck t=1 r=0~255 o=nearest\n#allocate write\n",
                "Invalid identifier.",
            ),
            (
                "#basicfuck t=0 r=0~255 o=nearest\n#allocate a\n",
                "Insufficient memory.",
            ),
            (H + "z += 1;", "Identifier is undefined."),
            (H + "a += ;", "Invalid syntax."),
        ):
            with raises_message(ValueError, message, code):
                run_program(code)

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
        assert (machine.frames[-1][1], list(machine.cells)) == (0, [0])
        machine.step()  # a += 65
        assert list(machine.cells) == [65]
        machine.step()  # write prints a
        assert machine.io.getvalue() == "A"
        machine.step()  # the finished frame is finalized
        assert machine.halted
        machine.step()  # stepping a halted machine is a no-op
        assert machine.frames == ()

    def test_a_frame_reports_what_kind_of_scope_it_is(self) -> None:
        """The snapshot carries each frame's loop bookkeeping, not just its
        cursor.

        A plain scope and a ``while`` owner differ only in those fields --
        ``loop``, the position its condition sits at, and whether that
        condition is negated -- so a snapshot that reported the cursor
        alone would call two different states equal and let the hang
        detector stop early.  Nothing else here reads them: the other
        snapshot test asserts only that the tuple can be hashed, and the
        checks that use the content go through the shared runner, which
        the bundled build does not inline.
        """
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.interpreters.tape_based.basicfuck import _Machine

        head = "#basicfuck t=2 r=0~255 o=nearest\n#allocate a, b\n"

        def frames_after(code: str, steps: int) -> tuple[object, ...]:
            machine = _Machine(head + code, ScriptedIO(""))
            for _ in range(steps):
                if machine.halted:
                    break
                machine.step()
            return machine.snapshot()[1]

        # the outermost frame is not a loop owner: no condition, not negated
        top = frames_after("a += 1;\n", 0)
        assert len(top) == 1
        _prog, ptr, loop, cond_pos, neg, body = top[0]
        assert (ptr, loop, cond_pos, neg, body) == (0, False, -1, False, None)

        # entering a while pushes a body frame and marks its owner
        owner, inner = None, None
        for step in range(1, 8):
            got = frames_after("a += 1;\nwhile (a) { a -= 1; }\n", step)
            if len(got) == 2:
                owner, inner = got
                break
        assert owner is not None
        assert inner is not None
        assert owner[2] is True  # the owner runs a loop
        assert owner[3] >= 0  # and knows where its condition is
        assert owner[5] is not None  # and holds the body to re-run
        assert inner[2] is False  # the body itself is an ordinary scope
        assert inner[5] is None

        # a negated loop is a different state from a plain one
        plain = frames_after("a += 1;\nwhile (a) { a -= 1; }\n", 2)
        negated = frames_after("a += 1;\nwhile !(a) { a += 1; }\n", 2)
        assert plain != negated


class TestDirectiveEdges:
    """The parts of the header that only an unusual directive reaches.

    A mutation run left 119 survivors, a third of them inside the header
    parser.  The suite drove it with one shape -- ``t=<n> r=<lo>~<hi>
    o=<mode>``, every field present -- so the branches that supply a
    *default* were never taken, and neither were the rules about which
    combinations are legal.
    """

    def test_an_omitted_bound_defaults_to_the_32_bit_limit(self) -> None:
        """``r=~`` leaves both bounds at the widest the interpreter allows.

        The defaults are ``-(2**31)`` and ``2**31 - 1``, and nothing else
        here reads them: a program that never approaches a bound cannot
        tell one default from another.  Constants are scanned as
        arbitrary-length digit runs, so a cell can be driven *to* the
        default bound and then brought back down into printable range,
        which reads the bound's exact value out as a byte.
        """
        top, bot = 2**31 - 1, 2**31
        assert (
            run_program(
                "#basicfuck t=1 r=~ o=nearest\n#allocate a\n"
                f"a += {top + 1000};\na -= {top - 65};\nwrite <- a;\n"
            )
            == "A"
        )
        assert (
            run_program(
                "#basicfuck t=1 r=~ o=nearest\n#allocate a\n"
                f"a -= {bot + 1000};\na += {bot + 66};\nwrite <- a;\n"
            )
            == "B"
        )
        # and each half-open form defaults only its missing side
        assert (
            run_program(
                "#basicfuck t=1 r=0~ o=nearest\n#allocate a\n"
                f"a += {top + 1000};\na -= {top - 67};\nwrite <- a;\n"
            )
            == "C"
        )
        assert (
            run_program(
                "#basicfuck t=1 r=~255 o=nearest\n#allocate a\n"
                f"a -= {bot + 1000};\na += {bot + 68};\nwrite <- a;\n"
            )
            == "D"
        )

    def test_a_bounded_range_must_say_what_overflow_does(self) -> None:
        """``o=`` is required exactly when a bound is given.

        One bound is enough to require it, which is the case that
        separates "any bound" from "both bounds" -- and an open range
        needs no mode at all.
        """
        with pytest.raises(ValueError, match=re.escape("Missing overflow directive.")):
            run_program("#basicfuck t=1 r=0~\n#allocate a\na += 65;\n")
        with pytest.raises(ValueError, match=re.escape("Missing overflow directive.")):
            run_program("#basicfuck t=1 r=~255\n#allocate a\na += 65;\n")
        assert (
            run_program("#basicfuck t=1 r=~\n#allocate a\na += 65;\nwrite <- a;\n")
            == "A"
        )

    def test_the_directives_are_rejected_by_name(self) -> None:
        """Each complaint names the thing that was wrong.

        The messages are asserted whole.  Every one of them is a literal
        that an edit can widen or recase, and a substring match would not
        notice.
        """
        for code, message in (
            ("", "Missing/Invalid directives."),
            ("#nonsense\n#allocate a\na += 1;\n", "Missing/Invalid directives."),
            # a mode the directive does not offer fails the whole pattern
            (
                "#basicfuck t=1 r=0~9 o=sideways\n#allocate a\na += 1;\n",
                "Missing/Invalid directives.",
            ),
            ("#allocate a\na += 1;\n", "Missing/Invalid directives."),
            ("#basicfuck t=1 r=0~255 o=nearest\n", "Missing/Invalid identifiers."),
            (
                "#basicfuck t=1 r=0~255 o=nearest\n#allocate 1bad\na += 1;\n",
                "Missing/Invalid identifiers.",
            ),
            (
                "#basicfuck t=1 r=0~255 o=nearest\n#allocate a, b, c\na += 1;\n",
                "Insufficient memory.",
            ),
            (
                "#basicfuck t=1 r=0~255\n#allocate a\na += 65;\n",
                "Missing overflow directive.",
            ),
        ):
            with pytest.raises(ValueError, match=re.escape(message)) as caught:
                run_program(code)
            assert str(caught.value) == message

        # an allocation line with nothing after it is a complete program
        assert run_program("#basicfuck t=1 r=0~255 o=nearest\n#allocate a") == ""

    def test_variable_arithmetic_reserves_a_scratch_cell(self) -> None:
        """``X += Y`` needs one cell beyond the allocations; ``X += 1`` does not.

        Adding a *variable* is compiled with a spare cell to work in, so a
        program that does it needs a tape one larger than its allocation
        list -- and one that only ever adds constants does not.  The
        reservation is conditional on the program actually containing such
        an assignment, which is the part a test using constants alone
        cannot see.
        """
        two = "#allocate a, b\na += 65;\nb += 1;\n"
        # adding a variable: two names need three cells
        with pytest.raises(ValueError, match=re.escape("Insufficient memory.")):
            run_program(f"#basicfuck t=2 r=0~255 o=nearest\n{two}a += b;\n")
        assert (
            run_program(
                f"#basicfuck t=3 r=0~255 o=nearest\n{two}a += b;\nwrite <- a;\n"
            )
            == "B"
        )
        # adding only constants: two names fit in two cells
        assert (
            run_program(f"#basicfuck t=2 r=0~255 o=nearest\n{two}write <- a;\n") == "A"
        )

    def test_the_tape_must_hold_every_allocation(self) -> None:
        """One cell per name, and the check is ``>`` not ``>=``.

        Exactly enough tape is enough; one less is not.  A bound that
        admitted an over-large allocation would let a later name index
        past the end of the tape.
        """
        for size in (1, 2, 3):
            names = ", ".join("abc"[:size])
            head = f"#basicfuck t={size} r=0~255 o=nearest\n#allocate {names}\n"
            assert run_program(head + "a += 65;\nwrite <- a;\n") == "A"
            short = f"#basicfuck t={size - 1} r=0~255 o=nearest\n#allocate {names}\n"
            with pytest.raises(ValueError, match=re.escape("Insufficient memory.")):
                run_program(short + "a += 1;\n")

    def test_a_keyword_cannot_be_an_identifier(self) -> None:
        """All four reserved words are rejected, not just the first.

        The check is a membership test against a tuple; a suite that tries
        only one of them cannot notice the other three going missing.
        """
        message = "Invalid identifier."
        for word in ("if", "while", "write", "read"):
            with pytest.raises(ValueError, match=re.escape(message)) as caught:
                run_program(
                    f"#basicfuck t=1 r=0~255 o=nearest\n#allocate {word}\n"
                    f"{word} += 1;\n"
                )
            assert str(caught.value) == message
        # a name that merely starts with a keyword is fine
        assert (
            run_program(
                "#basicfuck t=1 r=0~255 o=nearest\n#allocate iffy\n"
                "iffy += 65;\nwrite <- iffy;\n"
            )
            == "A"
        )


class TestOverflowAtBothBounds:
    """Each mode against each end of the range.

    The suite tested one direction per mode, so the arithmetic that picks
    *which* bound to clamp or wrap to was only ever exercised one way.
    """

    def test_halt_names_which_way_it_went(self) -> None:
        """Two different complaints, asserted whole."""
        for delta, message in (
            ("a += 12;", "Overflow error."),
            ("a -= 1;", "Underflow error."),
        ):
            with pytest.raises(HaltError, match=re.escape(message)) as caught:
                run_program(
                    f"#basicfuck t=1 r=0~9 o=halt\n#allocate a\n{delta}\nwrite <- a;\n"
                )
            assert str(caught.value) == message

    def test_wrap_lands_on_the_far_bound(self) -> None:
        """Wrapping goes to the *opposite* end, not round by the excess.

        Passing the top lands on the bottom and passing the bottom lands
        on the top, however far past it went -- so the two directions read
        each other's bound, and swapping them is what this catches.
        """
        for delta in ("a += 10;", "a += 12;", "a += 200;"):
            assert (
                run_program(
                    f"#basicfuck t=1 r=0~9 o=wrap\n#allocate a\n{delta}\nwrite <- a;\n"
                )
                == "\x00"
            )
        for delta in ("a -= 1;", "a -= 3;", "a -= 200;"):
            assert (
                run_program(
                    f"#basicfuck t=1 r=0~9 o=wrap\n#allocate a\n{delta}\nwrite <- a;\n"
                )
                == "\x09"
            )

    def test_landing_exactly_on_a_bound_is_in_range(self) -> None:
        """Both guards are strict, so a bound itself is a legal value.

        Every case above goes *past* a bound, where a strict comparison
        and a non-strict one agree.  A value landing exactly on one is
        what separates them: at 9 the cell keeps its value under all
        three modes, where a non-strict guard would halt, wrap to 0, or
        clamp instead.
        """
        for mode in ("halt", "wrap", "nearest"):
            assert (
                run_program(
                    f"#basicfuck t=1 r=0~9 o={mode}\n#allocate a\n"
                    "a += 9;\nwrite <- a;\n"
                )
                == "\x09"
            ), mode

    def test_wrap_needs_both_bounds(self) -> None:
        """``o=wrap`` has nowhere to wrap to unless the range is closed.

        This is the only route to the "invalid overflow directive"
        complaint: a misspelled mode fails the directive pattern instead,
        and is reported as a malformed directive.
        """
        for rng in ("r=0~", "r=~9", "r=~"):
            with pytest.raises(
                ValueError, match=re.escape("Invalid overflow directive.")
            ):
                run_program(
                    f"#basicfuck t=1 {rng} o=wrap\n#allocate a\na += 1;\nwrite <- a;\n"
                )
        assert (
            run_program(
                "#basicfuck t=1 r=0~9 o=wrap\n#allocate a\na += 1;\nwrite <- a;\n"
            )
            == "\x01"
        )

    def test_nearest_clamps_to_the_bound_it_passed(self) -> None:
        assert (
            run_program(
                "#basicfuck t=1 r=0~9 o=nearest\n#allocate a\na += 200;\nwrite <- a;\n"
            )
            == "\x09"
        )
        assert (
            run_program(
                "#basicfuck t=5 r=5~9 o=nearest\n#allocate a\na -= 200;\nwrite <- a;\n"
            )
            == "\x05"
        )


class TestLoopConditions:
    """A ``while`` re-tests its condition; a negated one tests the inverse.

    The suite looped only on a truthy counter running down.  A negated
    ``while`` runs while its cell is *zero*, so the two disagree about
    when to stop -- and the position the condition is read from differs
    between them, since ``!`` occupies a slot of its own.
    """

    def test_a_negated_while_runs_until_its_cell_is_set(self) -> None:
        assert (
            run_program(
                "#basicfuck t=2 r=0~255 o=nearest\n#allocate a, b\n"
                "b += 65;\nwhile !(a) { write <- b;\na += 1; }\n"
            )
            == "A"
        )

    def test_a_negated_while_may_never_run(self) -> None:
        assert (
            run_program(
                "#basicfuck t=2 r=0~255 o=nearest\n#allocate a, b\n"
                "a += 1;\nb += 65;\nwhile !(a) { write <- b; }\nwrite <- b;\n"
            )
            == "A"
        )

    def test_a_plain_while_counts_down(self) -> None:
        assert (
            run_program(
                "#basicfuck t=2 r=0~255 o=nearest\n#allocate a, b\n"
                "a += 3;\nb += 65;\nwhile (a) { write <- b;\na -= 1; }\n"
            )
            == "AAA"
        )


class TestAllocationOffsets:
    """Where each name lands on the tape.

    ``_index`` walks the allocation list adding each name's size.  With
    one variable in play a wrong offset is invisible: the cell it lands on
    is fresh either way, so whatever was written reads back.  It shows
    only when two names collide on one cell, which needs three
    allocations all in use.
    """

    def test_three_names_do_not_share_a_cell(self) -> None:
        assert (
            run_program(
                "#basicfuck t=4 r=0~255 o=nearest\n#allocate a, b, c\n"
                "a += 65;\nb += 66;\nc += 67;\n"
                "write <- a;\nwrite <- b;\nwrite <- c;\n"
            )
            == "ABC"
        )

    def test_an_array_after_a_variable_starts_past_it(self) -> None:
        assert (
            run_program(
                "#basicfuck t=8 r=0~255 o=nearest\n#allocate z, arr->3\n"
                "z += 65;\narr->2 += 66;\nwrite <- z;\nwrite <- arr->2;\n"
            )
            == "AB"
        )

    def test_an_index_past_the_array_is_caught(self) -> None:
        """Reading and writing past the tape both raise, at either end."""
        head = "#basicfuck t=8 r=0~255 o=nearest\n#allocate arr->3, z\n"
        message = "tape index out of bounds"
        for body in ("arr->9 += 1;\n", "z += arr->9;\n"):
            with pytest.raises(HaltError, match=re.escape(message)) as caught:
                run_program(head + body)
            assert str(caught.value) == message

    def test_an_unallocated_name_is_undefined(self) -> None:
        """``_index`` walks the whole list before giving up.

        The complaint comes from falling off the end of the allocation
        list, which a loop that stopped early would reach too soon.
        """
        message = "Identifier is undefined."
        with pytest.raises(ValueError, match=re.escape(message)) as caught:
            run_program("#basicfuck t=1 r=0~255 o=nearest\n#allocate a\nzz += 1;\n")
        assert str(caught.value) == message
        # and a name that IS allocated, but only after others, still resolves
        assert (
            run_program(
                "#basicfuck t=3 r=0~255 o=nearest\n#allocate a, b, c\n"
                "c += 67;\nwrite <- c;\n"
            )
            == "C"
        )


class TestLexerBoundaries:
    r"""Tokens that run to the very end of the source.

    The scanners are ``while j < n and program[j]...``.  Every existing
    test ends its program with a newline, which stops the whitespace skip
    one character early, so no scan ever reached the final character --
    and a bound loosened to ``<=`` would index past the end.

    ``_`` is an identifier character.  Removing it from the scan does not
    reject such a name; it makes the scan consume *nothing*, leaving the
    cursor where it was, so the tokenizer spins forever.  That happens
    inside the constructor, before any step, which is why it shows up as a
    hang rather than an error.
    """

    def test_a_name_may_be_or_contain_an_underscore(self) -> None:
        assert (
            run_program(
                "#basicfuck t=1 r=0~255 o=nearest\n#allocate _\n_ += 65;\nwrite <- _;\n"
            )
            == "A"
        )
        assert (
            run_program(
                "#basicfuck t=1 r=0~255 o=nearest\n#allocate a_b\n"
                "a_b += 66;\nwrite <- a_b;\n"
            )
            == "B"
        )

    def test_a_token_may_end_the_source(self) -> None:
        """No trailing newline, so the final character is part of a token."""
        head = "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\n"
        arrays = "#basicfuck t=8 r=0~255 o=nearest\n#allocate arr->3, z\n"
        message = "Invalid syntax."
        cases = [head + t for t in ("write <- a", "a", "a_", "a += 12", "a += 1")]
        # an array index running to the end, and a bare arrow
        cases += [arrays + "arr->2", arrays + "arr->"]
        for code in cases:
            with pytest.raises(ValueError, match=re.escape(message)) as caught:
                run_program(code)
            assert str(caught.value) == message

    def test_one_slash_is_not_a_comment(self) -> None:
        message = "Invalid token."
        with pytest.raises(ValueError, match=re.escape(message)) as caught:
            run_program(
                "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\n"
                "a += 65; / \nwrite <- a;\n"
            )
        assert str(caught.value) == message

    def test_a_statement_may_be_cut_short(self) -> None:
        """Running out of tokens is not the same as meeting a wrong one.

        The parser's lookaheads are ``ind + k < size``.  Every malformed
        program the suite had supplied a *wrong* token; none stopped with
        the cursor exactly at the end, which is where those bounds differ.
        """
        head = "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\n"
        for tail in (
            "if",
            "if !",
            "if (",
            "if (a",
            "if (a)",
            "if (a) {",
            "while",
            "while (a)",
            "write",
            "write <-",
            "read",
            "read ->",
            "a +=",
            "a -=",
        ):
            with pytest.raises(ValueError, match=re.escape("Invalid syntax.")):
                run_program(head + tail + "\n")


def _machine(code: object) -> object:
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.tape_based.basicfuck import _Machine

    return _Machine(code, ScriptedIO())


# The directives every program needs before its first statement.
_NEAREST = "#basicfuck t=1 r=0~255 o=nearest\n#allocate a\n"
_WRAP = "#basicfuck t=1 r=0~255 o=wrap\n#allocate a\n"


class TestContract(SnapshotContract, CycleContract):
    """The shared shapes. ``while (a)`` with a nonzero ``a`` never exits."""

    machine = staticmethod(_machine)
    stepping_program = _NEAREST
    halting_program = _NEAREST + "a += 1;"
    looping_program = _WRAP + "a += 1;\nwhile (a) { }"
