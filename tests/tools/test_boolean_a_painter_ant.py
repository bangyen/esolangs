"""Covers :mod:`esolangs.tools.a_painter_ant`, and the trace it is read from."""

from itertools import pairwise
from typing import ClassVar

import pytest

from esolangs.interpreters.grid_based.a_painter_ant import _Machine as _APAMachine
from esolangs.interpreters.grid_based.a_painter_ant import run as run_a_painter_ant
from esolangs.tools.a_painter_ant import _instantiate_apa, a_painter_ant


# 2.0s over 45 tests: runs the generated program.
@pytest.mark.medium
class TestAPainterAnt:
    """The A Painter Ant generator (a no-I/O grid language, parameterized convention).

    The interpreter prints the visited-cell bounding box (which carries no
    coordinates), so the Boolean answer is read from a small semantic grid
    model: the colour of the cell the ant lands on at the end of a cycle
    (white is one, black is zero), read after any whole number of cycles
    since every instantiated program is a cycle-stable fixed point.  ``n ==
    1`` pads to a two-input table with the second input fixed to zero;
    ``n >= 3`` uses the same piecewise head with more bits, and every arity
    is exact and cycle-stable (see ``the relevant generator tests``).
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
        """The template carries {X0} and {X1}, not hardcoded bits."""
        template = a_painter_ant("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_leaf_paint_omits_zero_subtrees(self) -> None:
        """A zero leaf is omitted and a one leaf is painted P.

        The generator never paints a cell black (no ``p``), which is what
        keeps every instantiated program a monotone, cycle-stable fixed
        point.
        """
        template = a_painter_ant("0110")  # f(1,1)=0, f(0,0)=0, f(1,0)=1, f(0,1)=1
        assert template.count("P") < a_painter_ant("1111").count("P")
        # no paint-black anywhere in any instantiated program
        program = _instantiate_apa(template, [1, 1])
        assert "p" not in program

    def test_all_one_input_functions(self) -> None:
        """Every one-input table is exact and cycle-stable for both inputs.

        n == 1 is supported by fixing the padded second input to zero and
        using the n == 2 construction with b1 == 0 (see
        :func:`a_painter_ant`).
        """
        for value in range(4):
            table = format(value, "02b")
            for bit in [0, 1]:
                assert self._check(table, [bit]) == int(table[bit]), (
                    f"table {table} bit {bit}"
                )

    def test_instantiate_one_bit_fills_single_placeholder(self) -> None:
        """An n == 1 template carries only {X0}, filled per bit."""
        template = a_painter_ant("01")  # f(0)=0, f(1)=1
        assert "{X0}" in template
        assert "{X1}" not in template
        assert _instantiate_apa(template, [1]) == template.replace("{X0}", "WWwWWEEe")
        assert _instantiate_apa(template, [0]) == template.replace("{X0}", "NENEESWw")

    def test_three_input_works(self) -> None:
        """AND3 is exact and cycle-stable on every input."""
        from itertools import product

        for bits in product([0, 1], repeat=3):
            table = "00000001"
            assert self._check(table, list(bits)) == int(
                table[bits[0] * 4 + bits[1] * 2 + bits[2]]
            ), f"AND3 bits {bits}"

    def test_four_input_head_works(self) -> None:
        """The head's leaf layout generalizes past three inputs."""
        from esolangs.tools.a_painter_ant import _leaf_positions

        positions = _leaf_positions(4)
        assert len(positions) == 16
        assert len({(x, y) for x, y, _ in positions}) == 16  # all distinct

    def test_leaf_coordinates_agree_with_the_moves_that_walk_them(self) -> None:
        """``_leaf_positions`` is the mirror of what ``_bit_move`` emits.

        The head reaches a leaf by walking ``_bit_move`` per bit, and the
        routing reads it at the coordinate ``_leaf_positions`` reports;
        the docstrings say the two always agree, and nothing checked it.
        Distinctness alone does not: perturbing the weight to
        ``2**(n-k+1)``, or swapping the axis parity, leaves all ``2**n``
        points distinct and every ``bits`` tuple unchanged, so the layout
        looks fine while the head walks somewhere the routing does not
        read.  Deriving the coordinate from the moves catches exactly that.

        The two are mirrored on **x only**: a set bit moves west
        (``-x``) but counts ``+2**(n-k)``, while on the vertical axis a set
        bit moves north and counts positive alike.  That asymmetry is the
        "mirror position" the docstring names, and pinning it is what makes
        an axis-parity flip visible.
        """
        from esolangs.tools.a_painter_ant import _bit_move, _leaf_positions

        step = {"w": (-1, 0), "e": (1, 0), "n": (0, 1), "s": (0, -1)}
        for n in (1, 2, 3, 4, 5):
            for x, y, bits in _leaf_positions(n):
                walked_x = walked_y = 0
                for k, bit in enumerate(bits):
                    for move in _bit_move(n, k, bit):
                        dx, dy = step[move]
                        walked_x += dx
                        walked_y += dy
                assert (walked_x, walked_y) == (-x, y), (n, bits)

    def test_leaf_coordinates_are_the_weighted_grid(self) -> None:
        """Each bit contributes ``+-2**(n-k)`` on the axis its index picks.

        Pinned exactly at two and three inputs, since the weight and the
        axis choice are both invisible to a distinctness check and to
        every behavioural assertion in this class -- the head only consumes
        the ``bits`` field.
        """
        from esolangs.tools.a_painter_ant import _leaf_positions

        assert _leaf_positions(2) == [
            (-2, -4, (0, 0)),
            (2, -4, (0, 1)),
            (-2, 4, (1, 0)),
            (2, 4, (1, 1)),
        ]
        assert [(x, y) for x, y, _ in _leaf_positions(3)] == [
            (-10, -4),
            (-6, -4),
            (-10, 4),
            (-6, 4),
            (6, -4),
            (10, -4),
            (6, 4),
            (10, 4),
        ]

    def test_four_and_five_input_generator_works(self) -> None:
        """The generator handles n == 4 and n == 5, exact and cycle-stable."""
        from itertools import product

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

    def test_shared_head_growth(self) -> None:
        """Wide dense tables grow no faster than their table size."""
        sizes = [len(a_painter_ant("1" * (2**n))) for n in range(6, 10)]
        assert all(b <= 2 * a for a, b in pairwise(sizes))

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
        from itertools import product

        for bits in product([0, 1], repeat=3):
            table = "01101001"
            assert self._check(table, list(bits)) == int(
                table[bits[0] * 4 + bits[1] * 2 + bits[2]]
            ), f"XOR3 bits {bits}"

    def test_non_binary_rejected(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            a_painter_ant("0123")

    def test_instantiate_fills_bits(self) -> None:
        """{X0} fills nnnn/ssss (the 2^(n-i)=4 weight) and {X1} fills the E/W dance."""
        template = a_painter_ant("0110")
        assert _instantiate_apa(template, [1, 1]) == template.replace(
            "{X0}",
            "nnnn",
        ).replace("{X1}", "WWwWWEEe")
        assert _instantiate_apa(template, [0, 0]) == template.replace(
            "{X0}",
            "ssss",
        ).replace("{X1}", "NENEESWw")


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


class TestLinearFill:
    """The wide-table fill is a setter: one step per unit of weight."""

    def test_each_slot_is_its_weight_in_steps(self) -> None:
        n = 5
        template = a_painter_ant("01" * 16)
        assert template.endswith("sS")
        zeros = _instantiate_apa(template, [0] * n)
        for i in range(n):
            bits = [0] * n
            bits[i] = 1
            ones = _instantiate_apa(template, bits)
            assert len(ones) == len(zeros)
            weight = 1 << (n - 1 - i)
            differing = [
                k for k, (a, b) in enumerate(zip(zeros, ones, strict=True)) if a != b
            ]
            assert len(differing) == weight
            assert {ones[k] for k in differing} == {"E"}
            assert {zeros[k] for k in differing} == {"e"}


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
