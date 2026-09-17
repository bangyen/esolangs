"""Covers :mod:`esolangs.tools.a_painter_ant`, and the trace it is read from."""

from itertools import pairwise, product
from typing import ClassVar

import pytest

from esolangs.interpreters.grid_based.a_painter_ant import _Machine as _APAMachine
from esolangs.interpreters.grid_based.a_painter_ant import run as run_a_painter_ant
from esolangs.tools.a_painter_ant import PAIR, a_painter_ant
from esolangs.tools.helpers import TEMPLATE_CHAR, runs
from tests.tools.fills import _instantiate_apa


# 2.0s over 45 tests: runs the generated program.
@pytest.mark.medium
class TestAPainterAnt:
    """The A Painter Ant generator (a no-I/O grid language, parameterized convention).

    The interpreter prints the visited-cell bounding box (which carries no
    coordinates), so the Boolean answer is read from a small semantic grid
    model: the colour of the cell the ant lands on at the end of a cycle
    (white is one, black is zero), read after any whole number of cycles
    since every instantiated program is a cycle-stable fixed point.  One
    construction serves every arity: a white corridor of ``2**n`` cells
    with the answers in the row below, each input one character (``n`` or
    ``N``) and its weight the ``E`` walk the template spells after it.
    """

    _MOVE: ClassVar[dict[str, tuple[int, int]]] = {
        "n": (0, -1),
        "e": (1, 0),
        "s": (0, 1),
        "w": (-1, 0),
    }

    @staticmethod
    def _landing_after(program: str, cycles: int = 6) -> int:
        """Landing cell colour (1 white, 0 black) after ``cycles`` cycles.

        Whitespace is ignored (the interpreter strips it), and the ant runs
        the program in an implicit loop; after each whole cycle the ant rests
        on its output leaf, whose colour is the Boolean answer.
        """
        prog = [c for c in program if not c.isspace()]
        grid: dict[tuple[int, int], int] = {}
        x = y = 0
        for _ in range(cycles * len(prog)):
            for command in prog:
                if command == "p":
                    grid[(x, y)] = 0
                elif command == "P":
                    grid[(x, y)] = 1
                else:
                    dx, dy = TestAPainterAnt._MOVE[command.lower()]
                    if (grid.get((x + dx, y + dy), 0) == 1) == command.isupper():
                        x += dx
                        y += dy
        return grid.get((x, y), 0)

    @staticmethod
    def _cycle_stable(program: str) -> bool:
        """``run()``'s auto-detected render agrees with a render pinned to ten cycles.

        ``run()`` renders at the first pass boundary whose state repeats;
        pinning a second render to ten cycles by hand and comparing is a
        stronger check than trusting the auto-detection alone, since it is
        an independent computation of the same claim -- that whichever pass
        the repeat is found at, every later pass renders identically.
        """
        from esolangs.interpreters.io import ScriptedIO

        io = ScriptedIO()
        run_a_painter_ant(program, io)
        return io.getvalue() == _render_after_passes(program, 10)

    @classmethod
    def _check(cls, table: str, bits: list[int]) -> int:
        program = _instantiate_apa(a_painter_ant(table), bits)
        assert cls._cycle_stable(program), f"{table} {bits}: not cycle-stable"
        return cls._landing_after(program)

    @pytest.mark.slow  # 1.2s: builds and runs all sixteen tables on four rows
    def test_all_two_input_functions(self) -> None:
        """Every two-input table is exact and cycle-stable for every input.

        ``test_xor`` and ``test_nand`` below spot-check the same builder in
        milliseconds, so the fast run still covers this path; this is the
        exhaustive sweep.
        """
        for value in range(16):
            table = format(value, "04b")
            for row in range(4):
                bits = [(row >> 1) & 1, row & 1]
                assert self._check(table, bits) == int(table[row]), (
                    f"{table} bits {bits}"
                )

    def test_xor(self) -> None:
        """XOR (0110) is one of the expressible tables."""
        assert self._check("0110", [0, 0]) == 0
        assert self._check("0110", [0, 1]) == 1
        assert self._check("0110", [1, 0]) == 1
        assert self._check("0110", [1, 1]) == 0

    def test_nand(self) -> None:
        """NAND (1110) is expressible."""
        assert self._check("1110", [0, 0]) == 1
        assert self._check("1110", [1, 1]) == 0

    def test_constant_tables(self) -> None:
        """Constant zero and one are expressible."""
        assert self._check("0000", [0, 0]) == 0
        assert self._check("0000", [1, 1]) == 0
        assert self._check("1111", [0, 0]) == 1
        assert self._check("1111", [1, 1]) == 1

    def test_template_has_input_placeholders(self) -> None:
        """The template carries one run per input, not hardcoded bits."""
        template = a_painter_ant("0110")
        assert "{X" not in template
        setters = (PAIR,) * 2
        assert template.count(TEMPLATE_CHAR) == sum(len(zero) for zero, _ in setters)
        assert len(runs(template, TEMPLATE_CHAR, setters)) == 2

    def test_zero_answers_are_not_painted(self) -> None:
        """A one answer is painted ``P``; a zero answer is left black.

        The generator never paints a cell black (no ``p``), which is what
        keeps every instantiated program a monotone, cycle-stable fixed
        point.
        """
        template = a_painter_ant("0110")
        assert template.count("P") < a_painter_ant("1111").count("P")
        # no paint-black anywhere in any instantiated program
        program = _instantiate_apa(template, [1, 1])
        assert "p" not in program

    def test_all_one_input_functions(self) -> None:
        """Every one-input table is exact and cycle-stable for both inputs."""
        for value in range(4):
            table = format(value, "02b")
            for bit in [0, 1]:
                assert self._check(table, [bit]) == int(table[bit]), (
                    f"table {table} bit {bit}"
                )

    def test_instantiate_one_bit_fills_single_placeholder(self) -> None:
        """An n == 1 template carries one run, filled per bit."""
        template = a_painter_ant("01")  # f(0)=0, f(1)=1
        assert len(runs(template, TEMPLATE_CHAR, (PAIR,) * 1)) == 1
        assert template.count(TEMPLATE_CHAR) == 1
        assert _instantiate_apa(template, [1]) == template.replace(TEMPLATE_CHAR, "N")
        assert _instantiate_apa(template, [0]) == template.replace(TEMPLATE_CHAR, "n")

    def test_three_input_works(self) -> None:
        """AND3 is exact and cycle-stable on every input."""
        for bits in product([0, 1], repeat=3):
            table = "00000001"
            assert self._check(table, list(bits)) == int(
                table[bits[0] * 4 + bits[1] * 2 + bits[2]]
            ), f"AND3 bits {bits}"

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

    def test_the_template_carries_each_weight(self) -> None:
        """Input ``i``'s run is followed by ``2**(n-1-i)`` ``E`` and ``SN``.

        The walk is the weight and the ``SN`` is the return to the
        corridor; the ``sS`` after the last one steps onto the answer.
        """
        template = a_painter_ant("01" * 16)  # n = 5
        head, *tails = template.split(TEMPLATE_CHAR)
        assert head.endswith("W" * 31)
        assert tails == [
            "E" * 16 + "SN",
            "E" * 8 + "SN",
            "E" * 4 + "SN",
            "E" * 2 + "SN",
            "E" * 1 + "SNsS",
        ]

    def test_each_input_moves_the_ant_by_its_weight(self) -> None:
        """After input ``i``'s gadget the ant stands at the partial index.

        Traced on the semantic model: a one walks the corridor by the
        weight, a zero steps into the black lane and is walked nowhere,
        and both end the gadget back on the corridor row.
        """
        from tests.tools.a_painter_ant_trace import run

        n = 4
        template = a_painter_ant("0110100110010110")
        first = template.index(TEMPLATE_CHAR)
        for bits in product([0, 1], repeat=n):
            program = _instantiate_apa(template, list(bits))
            steps = run(program, 1).steps
            partial = 0
            cursor = first
            for i, bit in enumerate(bits):
                partial += bit << (n - 1 - i)
                cursor += 1 + (1 << (n - 1 - i)) + 2  # the run, the walk, SN
                assert steps[cursor - 1].position == (partial, 0), (bits, i)

    def test_wide_tables_are_exact(self) -> None:
        """The construction handles n == 4 and n == 5, exact and cycle-stable."""
        from tests.tools.a_painter_ant_trace import cycle_stable, landing_after

        tables = {
            4: ["0000000000000001", "0110100110010110", "1111111111111111"],
            5: ["00000000000000000000000000000001"],
        }
        for n, table_list in tables.items():
            for table in table_list:
                template = a_painter_ant(table)
                for bits in product([0, 1], repeat=n):
                    program = _instantiate_apa(template, list(bits))
                    assert cycle_stable(program), f"n={n} bits {bits} not stable"
                    assert landing_after(program, 1) == int(
                        table[sum(bits[k] << (n - 1 - k) for k in range(n))]
                    ), f"n={n} table {table} bits {bits}"

    def test_size_growth(self) -> None:
        """Wide dense tables grow no faster than their table size.

        The two ``W`` walks cost two characters per entry, the corridor and
        its answers seven, the walks one per entry, and each input three more:
        doubling the table doubles the size and adds that constant back.
        """
        sizes = [len(a_painter_ant("1" * (2**n))) for n in range(6, 10)]
        assert all(b <= 2 * a + 3 for a, b in pairwise(sizes))
        assert sizes[0] == 1 + (64 + 63) + (7 * 64 - 3) + 63 + 3 * 6 + 2

    def test_linear_strip_executes_dense_wide_table(self) -> None:
        """Every row reaches its adjacent strip cell and remains cycle-stable."""
        from tests.tools.a_painter_ant_trace import cycle_stable, landing_after

        n = 6
        table = "".join(str((row.bit_count() ^ (row >> 2)) & 1) for row in range(2**n))
        template = a_painter_ant(table)
        for row in range(2**n):
            bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
            program = _instantiate_apa(template, bits)
            assert cycle_stable(program), row
            assert landing_after(program) == int(table[row]), row

    def test_three_input_xor_works(self) -> None:
        """XOR3 is exact and cycle-stable on every input."""
        for bits in product([0, 1], repeat=3):
            table = "01101001"
            assert self._check(table, list(bits)) == int(
                table[bits[0] * 4 + bits[1] * 2 + bits[2]]
            ), f"XOR3 bits {bits}"

    def test_non_binary_rejected(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            a_painter_ant("0123")

    def test_instantiate_fills_bits(self) -> None:
        """Every run fills to ``n`` for a zero and ``N`` for a one."""
        template = a_painter_ant("0110")
        assert PAIR == ("n", "N")
        assert template.count(TEMPLATE_CHAR) == 2
        assert _instantiate_apa(template, [1, 1]) == template.replace(
            TEMPLATE_CHAR, "N"
        )
        assert _instantiate_apa(template, [0, 0]) == template.replace(
            TEMPLATE_CHAR, "n"
        )
        mixed = template.replace(TEMPLATE_CHAR, "n", 1).replace(TEMPLATE_CHAR, "N")
        assert _instantiate_apa(template, [0, 1]) == mixed


def _shapes(n: int) -> tuple[str, str]:
    """The conventions audit's two table shapes at arity ``n``."""
    parity = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(2**n))
    dense = "".join("1" if (i * 7 + 3) % 5 < 2 else "0" for i in range(2**n))
    return parity, dense


def _render_after_passes(program: str, passes: int) -> str:
    """Render after exactly ``passes`` whole cycles, stepped by hand.

    ``run()`` no longer takes a pass count -- it steps until the state
    repeats at a boundary and renders there -- so this is what ``cycles=``
    used to give directly: a render pinned to a specific pass count, for
    comparing against ``run()``'s own auto-detected one.  Shared by both
    test classes below, so it lives at module scope rather than as a
    private method one borrows from the other.
    """
    machine = _APAMachine(program)
    span = len(machine.prog)
    for _ in range(passes * span):
        machine.step()
    return machine.render()


class TestAPainterAntTrace:
    """The A Painter Ant step tracer and cycle-stability checker.

    The tracer exposes the semantic grid model the generator reads its
    answer from, with per-instruction step records so a diverging cycle can
    be pinned to the exact instruction.  Its bounding-box renderer must
    agree with the interpreter's, and its stability verdict must agree with
    the interpreter's box across cycle counts.
    """

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

    def test_box_matches_the_interpreter(self) -> None:
        from itertools import product

        from esolangs.interpreters.io import ScriptedIO
        from tests.tools.a_painter_ant_trace import box

        for value in range(16):
            table = format(value, "04b")
            for bits in product([0, 1], repeat=2):
                program = _instantiate_apa(a_painter_ant(table), list(bits))
                io = ScriptedIO()
                run_a_painter_ant(program, io)
                assert box(program, 1) == io.getvalue().rstrip("\n"), (
                    table,
                    bits,
                )

    def test_cycle_stable_agrees_with_the_interpreter(self) -> None:
        from itertools import product

        from esolangs.interpreters.io import ScriptedIO
        from tests.tools.a_painter_ant_trace import cycle_stable

        for value in range(16):
            table = format(value, "04b")
            for bits in product([0, 1], repeat=2):
                program = _instantiate_apa(a_painter_ant(table), list(bits))
                assert cycle_stable(program), (table, bits)
                io = ScriptedIO()
                run_a_painter_ant(program, io)
                reference = io.getvalue()
                assert _render_after_passes(program, 10) == reference, (
                    table,
                    bits,
                )

    def test_cycle_stable_detects_a_divergence(self) -> None:
        from tests.tools.a_painter_ant_trace import cycle_stable

        assert not cycle_stable("nPn")  # each cycle paints one cell further

    def test_landing_after(self) -> None:
        from tests.tools.a_painter_ant_trace import landing_after

        assert landing_after(_instantiate_apa(a_painter_ant("0110"), [0, 1])) == 1
        assert landing_after(_instantiate_apa(a_painter_ant("0110"), [1, 1])) == 0

    def test_first_divergence_stable_program_is_none(self) -> None:
        from itertools import product

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
