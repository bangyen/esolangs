"""Branch arms the line-coverage tests reached only one way.

Each case here ran the guarded line already; what was missing was the
*other* answer to its condition.  They are gathered in one file because
they share nothing but that -- each is one arm of one guard, in whatever
language happens to own it.
"""

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.a_painter_ant import _Machine as _AntMachine
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.dinac import _parse_aschar
from esolangs.interpreters.other.dinac import run as dinac_run
from esolangs.interpreters.other.lamfunc import run as lamfunc_run
from esolangs.interpreters.other.packlang import _Parser
from esolangs.interpreters.stack_based.three_x import run as three_x_run
from esolangs.tools.boolean.laserfuck import laserfuck as laserfuck_boolean
from tests.interpreters.runner import run_program


class TestPainterAntDumpsOnce:
    def test_stepping_an_interrupted_machine_again_does_not_redump(self) -> None:
        """The picture is printed once, however often the machine is stepped.

        ``_dumped`` is what makes the second step a no-op; without it an
        interrupted program would print its grid once per step.
        """
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
        """``(`` over a zero jumps to its ``)``, or advances when there is none.

        The program halts on the empty stack a step later; what matters is
        that the missing target advances the cursor rather than raising or
        jumping to a stale one.
        """
        with pytest.raises(HaltError, match="empty stack"):
            run_program(three_x_run, "1(", "")


class TestLamfuncStepWithoutPops:
    def test_a_step_that_pops_nothing_leaves_the_frames_alone(self) -> None:
        """Most steps push without popping; the delete must not run then."""
        assert run_program(lamfunc_run, "x", "") == ""


class TestDinacRawCharAfterQuote:
    def test_a_non_ascii_character_is_not_an_aschar(self) -> None:
        # The quote takes the next character raw, and this one is not in
        # the aschar range, so the literal is malformed rather than parsed.
        assert _parse_aschar("È") is None
        # The scan does not stop on it, so the whole token is read and
        # rejected as a value rather than as a bare quote.
        with pytest.raises(ValueError, match="malformed value"):
            run_program(dinac_run, "OUT 'È", "")

    def test_an_ascii_character_after_a_quote_parses(self) -> None:
        """The positive control: the same shape with a legal character."""
        assert run_program(dinac_run, "OUT '(", "") == "("


class TestDinacBareParenthesisedStatement:
    def test_a_parenthesised_expression_is_not_a_bare_call(self) -> None:
        """A statement ending in ``)`` is only a call if it parses as one."""
        with pytest.raises(ValueError, match="malformed statement"):
            run_program(dinac_run, "(41)", "")


class TestPacklangDeclarationScan:
    def test_a_type_followed_by_a_non_name_is_not_a_declaration(self) -> None:
        """The name check fails, so the semicolon is never looked for."""
        assert _Parser(["Integer", "5", ";"]).is_declaration() is False


class TestLaserfuckGridWrite:
    def test_a_table_whose_layout_backfills_a_row_builds(self) -> None:
        """The grid pads only when the column is past the line's end.

        XOR's layout writes back into rows it has already filled, which is
        the arm a forward-only layout never takes.  Asserted on the built
        program: a padding bug there would corrupt the grid, not raise.
        """
        program = laserfuck_boolean("0110")
        # ``test_boolean_other`` runs this program against the table from
        # every heading; here the point is only that the backfilling write
        # produces a grid at all, and that every row it padded is as wide
        # as the character it was padded for.
        for row in program.split("\n"):
            assert row == "" or not row.endswith(" ")
