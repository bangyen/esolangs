"""Covers :mod:`esolangs.tools.a_painter_ant`, and the trace it is read from."""

from itertools import pairwise, product

import pytest

from esolangs.tools.a_painter_ant import PAIR, a_painter_ant
from esolangs.tools.helpers import TEMPLATE_CHAR
from tests.tools.fills import _instantiate_apa


class TestAPainterAnt:
    """Input-pair convention, emitted sizes, and malformed tables."""

    def test_every_input_is_the_one_pair(self) -> None:
        """Uniform: the same ``(n, N)`` pair for every input at every arity.

        The conventions audit reads this off the programs; here it is
        pinned at the source, on both of its table shapes, so that a route
        that spelled an input's weight into its embed again would fail
        here before it failed there.
        """
        for n in range(1, 7):
            for table in _shapes(n):
                template = a_painter_ant(table)
                assert PAIR == ("n", "N")
                assert template.count(TEMPLATE_CHAR) == n

    def test_size_growth(self) -> None:
        """Wide dense tables grow no faster than their table size.

        The two ``W`` walks cost two characters per entry, the corridor and
        its answers six, the walks one per entry, and each input three more:
        doubling the table doubles the size and adds that constant back.  The
        last answer differs from the one before, so the corridor is whole.
        """
        sizes = [len(a_painter_ant("1" * (2**n - 1) + "0")) for n in range(6, 10)]
        assert all(b <= 2 * a + 3 for a, b in pairwise(sizes))
        assert sizes[0] == 1 + (63 + 63) + (6 * 64 - 5) + 63 + 3 * 6 + 1

    def test_three_input_total(self) -> None:
        """The 256 three-input templates total 15,245 characters.

        19,200 before the head's ``W`` walk stopped at the corridor's last
        cell, each corridor cell dropped its second ``P``, and the closing
        ``S`` went (a white answer reads off the white corridor above it);
        16,896 before the corridor stopped where the trailing run starts.
        """
        total = sum(len(a_painter_ant(f"{value:08b}")) for value in range(256))
        assert total == 15245

    def test_non_binary_rejected(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            a_painter_ant("0123")


def _shapes(n: int) -> tuple[str, str]:
    """The conventions audit's two table shapes at arity ``n``."""
    parity = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(2**n))
    dense = "".join("1" if (i * 7 + 3) % 5 < 2 else "0" for i in range(2**n))
    return parity, dense


class TestAPainterAntTrace:
    """Trace diagnostics and divergence attribution."""

    def test_run_records_moves_blocks_and_paints(self) -> None:
        from tests.tools.a_painter_ant_trace import run

        outcome = run("nNPp", 1)
        assert [s.action for s in outcome.steps] == [
            "moved",
            "blocked",
            "paint_white",
            "paint_black",
        ]
        assert outcome.steps[0].target == (0, -1)
        assert outcome.steps[1].position == (0, -1)
        assert outcome.steps[2].position == (0, -1)
        assert outcome.steps[3].position == (0, -1)
        assert outcome.steps[0].command == "n"
        assert outcome.steps[0].index == 0
        assert outcome.grid[(0, -1)] == 0  # p repaints the white cell black
        assert outcome.visited == {(0, 0), (0, -1)}
        assert outcome.position == (0, -1)

    def test_run_ignores_whitespace(self) -> None:
        from tests.tools.a_painter_ant_trace import run

        assert [s.command for s in run("n n  P", 1).steps] == ["n", "n", "P"]

    def test_run_rejects_unknown_instruction(self) -> None:
        from tests.tools.a_painter_ant_trace import run

        with pytest.raises(ValueError, match="unknown instruction"):
            run("nPx", 1)

    def test_run_records_landings_per_cycle(self) -> None:
        from tests.tools.a_painter_ant_trace import run

        assert run("nP", 3).landings == [(0, -1), (0, -2), (0, -3)]

    def test_landing_colour(self) -> None:
        from tests.tools.a_painter_ant_trace import run

        assert run("nP", 1).landing_colour() == 1  # (0,-1) was painted white
        assert run("n", 1).landing_colour() == 0  # (0,-1) is still black

    def test_cycle_stable_detects_a_divergence(self) -> None:
        from tests.tools.a_painter_ant_trace import cycle_stable

        assert not cycle_stable("nPn")  # each cycle paints one cell further

    def test_landing_after(self) -> None:
        from tests.tools.a_painter_ant_trace import landing_after

        assert landing_after(_instantiate_apa(a_painter_ant("0110"), [0, 1])) == 1
        assert landing_after(_instantiate_apa(a_painter_ant("0110"), [1, 1])) == 0

    def test_first_divergence_stable_program_is_none(self) -> None:

        from tests.tools.a_painter_ant_trace import first_divergence

        for bits in product([0, 1], repeat=2):
            program = _instantiate_apa(a_painter_ant("0110"), list(bits))
            assert first_divergence(program) is None, bits

    def test_first_divergence_pins_a_box_escape(self) -> None:
        from tests.tools.a_painter_ant_trace import first_divergence

        divergence = first_divergence("nPn")  # cycle 2 moves to (0,-3), outside
        assert divergence is not None
        assert divergence.index == 0
        assert divergence.command == "n"
        assert divergence.position == (0, -3)
        assert divergence.step1.position == (0, -1)
        assert divergence.step2.position == (0, -3)

    def test_first_divergence_pins_a_paint_break(self) -> None:
        from tests.tools.a_painter_ant_trace import first_divergence

        divergence = first_divergence("Pn")  # cycle 2 paints the black (0,-1)
        assert divergence is not None
        assert divergence.index == 0
        assert divergence.command == "P"
        assert divergence.step1.position == (0, 0)
        assert divergence.step2.position == (0, -1)

    def test_first_divergence_pins_a_changed_answer(self) -> None:
        from tests.tools.a_painter_ant_trace import first_divergence

        # cycle 1 lands white on (0,-1); cycle 2 slides onto the black (0,0)
        divergence = first_divergence("nPnPsS")
        assert divergence is not None
        assert divergence.index == 5
        assert divergence.command == "S"
        assert divergence.step1.position == (0, -1)
        assert divergence.step2.position == (0, 0)

    def test_first_divergence_pins_a_drifting_dance(self) -> None:
        from tests.tools.a_painter_ant_trace import first_divergence

        # cycle 2 lands on (0,0) instead of (0,1): same colour, but the dance
        # is not a fixed point and cycle 3 differs from cycle 2
        divergence = first_divergence("NPsP")
        assert divergence is not None
        assert divergence.index == 0
        assert divergence.command == "N"
        assert divergence.step1.action == "moved"
        assert divergence.step2.action == "blocked"
