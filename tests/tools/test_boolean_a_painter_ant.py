"""Covers :mod:`esolangs.tools.a_painter_ant`, and the trace it is read from."""

from itertools import product

import pytest

import esolangs
from esolangs.interpreters.grid_based.a_painter_ant import run as run_a_painter_ant
from esolangs.tools.a_painter_ant import PAIR, a_painter_ant
from esolangs.tools.helpers import TEMPLATE_CHAR, runs
from tests.support.witness_tables import parity as _parity
from tests.tools.fills import fill

_instantiate_apa = fill("A Painter Ant")

_MOVE = {"n": (0, -1), "e": (1, 0), "s": (0, 1), "w": (-1, 0)}


def _landing_after(program: str, cycles: int = 6) -> int:
    """Landing cell colour (1 white, 0 black) after ``cycles`` cycles."""
    prog = [c for c in program if not c.isspace()]
    grid: dict[tuple[int, int], int] = {}
    x = y = 0
    for _ in range(cycles):
        for command in prog:
            if command == "p":
                grid[(x, y)] = 0
            elif command == "P":
                grid[(x, y)] = 1
            else:
                dx, dy = _MOVE[command.lower()]
                if (grid.get((x + dx, y + dy), 0) == 1) == command.isupper():
                    x += dx
                    y += dy
    return grid.get((x, y), 0)


def _check(table: str, bits: list[int]) -> int:
    return _landing_after(_instantiate_apa(a_painter_ant(table), bits))


# 2.0s over 45 tests: runs the generated program.
@pytest.mark.medium
class TestAPainterAnt:
    """The A Painter Ant generator: a no-I/O grid language, parameterized."""

    def test_tables_are_exact(self) -> None:
        """Every table at arity 1-3, and wide tables at 4-6, are exact."""
        for n in (1, 2):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                for row in range(1 << n):
                    bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
                    assert _check(table, bits) == int(table[row]), (table, bits)
        for table in ("00000001", "01101001"):
            for combo in product([0, 1], repeat=3):
                index = combo[0] * 4 + combo[1] * 2 + combo[2]
                assert _check(table, list(combo)) == int(table[index]), (table, combo)
        wide = {
            4: ["0110100110010110", "1111111111111111"],
            5: ["00000000000000000000000000000001"],
            6: ["".join(str((r.bit_count() ^ (r >> 2)) & 1) for r in range(64))],
        }
        for n, tables in wide.items():
            for table in tables:
                for row in range(1 << n):
                    bits = [(row >> (n - 1 - k)) & 1 for k in range(n)]
                    assert _check(table, bits) == int(table[row]), (n, table, bits)

    def test_template_shape_and_fill(self) -> None:
        """One run per input, filled per bit; zeros are never painted ``P``."""
        template = a_painter_ant("0110")
        assert PAIR == ("n", "N")
        assert "{X" not in template
        assert template.count(TEMPLATE_CHAR) == 2
        assert len(runs(template, TEMPLATE_CHAR, (PAIR,) * 2)) == 2
        assert _instantiate_apa(template, [1, 1]) == template.replace(
            TEMPLATE_CHAR, "N"
        )
        mixed = template.replace(TEMPLATE_CHAR, "n", 1).replace(TEMPLATE_CHAR, "N")
        assert _instantiate_apa(template, [0, 1]) == mixed
        assert "p" not in _instantiate_apa(template, [1, 1])
        # Input i's run is followed by 2**(n-1-i) E's and SN; the corridor
        assert a_painter_ant(_parity(3)).split(TEMPLATE_CHAR)[1:] == [
            "E" * 4 + "SN",
            "E" * 2 + "SN",
            "E" * 1 + "SNs",
        ]
        assert a_painter_ant("0111").split(TEMPLATE_CHAR)[0].startswith("NWP")


@pytest.mark.medium
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_roots_keep_one_origin(bit: str) -> None:
    """A constant table restores each input to one white origin, then leaves it."""
    from esolangs._evaluate import _evaluate

    table = bit * 8
    assert a_painter_ant(table) == "P" + "$S" * 3 + ("p" if bit == "0" else "")
    for options in ({}, {"width": 40}, {"balance": True}):
        program = esolangs.generate("A Painter Ant", table, **options)
        assert _evaluate("A Painter Ant", program, inputs=3) == table


class TestAPainterAntTrace:
    """The A Painter Ant step tracer and cycle-stability checker."""

    def test_run_records_steps_screen_and_landings(self) -> None:
        from tests.tools.a_painter_ant_trace import run

        outcome = run("nNPp", 1)
        assert [s.action for s in outcome.steps] == [
            "moved",
            "blocked",
            "paint_white",
            "paint_black",
        ]
        assert (outcome.steps[0].command, outcome.steps[0].index) == ("n", 0)
        assert outcome.steps[0].target == (0, -1)
        assert outcome.grid[(0, -1)] == 0
        assert outcome.position == (0, -1)
        assert [s.command for s in run("n n  P", 1).steps] == ["n", "n", "P"]
        assert run("nP", 3).landings == [(0, -1), (0, -2), (0, -3)]
        assert run("nP", 1).landing_colour() == 1
        with pytest.raises(ValueError, match="unknown instruction"):
            run("nPx", 1)

    def test_trace_agrees_with_the_interpreter(self) -> None:
        from esolangs.interpreters.io import ScriptedIO
        from tests.tools.a_painter_ant_trace import box, cycle_stable, first_divergence

        for value in range(16):
            table = format(value, "04b")
            for bits in product([0, 1], repeat=2):
                program = _instantiate_apa(a_painter_ant(table), list(bits))
                io = ScriptedIO()
                run_a_painter_ant(program, io)
                assert cycle_stable(program), (table, bits)
                assert box(program, 1) == io.getvalue().rstrip("\n"), (table, bits)
                if table == "0110":
                    assert first_divergence(program) is None
        assert not cycle_stable("nPn")
        assert not cycle_stable("Pn")
        divergence = first_divergence("nPn")  # cycle 2 moves outside the box
        assert divergence is not None
        assert (divergence.index, divergence.command) == (0, "n")
