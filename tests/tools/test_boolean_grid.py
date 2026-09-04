"""Unit tests for the grid-based boolean generators.

Covers :mod:`esolangs.tools.boolean.a_painter_ant` and
:mod:`esolangs.tools.boolean.wii2d`, whose programs are two-dimensional
grids rather than instruction strings.
"""

import importlib
import io
from contextlib import redirect_stdout
from typing import ClassVar
from unittest.mock import patch

import pytest

from esolangs.interpreters.grid_based.a_painter_ant import _Machine as _APAMachine
from esolangs.interpreters.grid_based.a_painter_ant import run as run_a_painter_ant
from esolangs.interpreters.io import IO
from esolangs.tools import boolean
from esolangs.tools.boolean.a_painter_ant import _instantiate_apa, a_painter_ant


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


class TestAPainterAnt:
    """The A Painter Ant generator (a no-I/O grid language, parameterized convention).

    The interpreter prints the visited-cell bounding box (which carries no
    coordinates), so the Boolean answer is read from a small semantic grid
    model: the colour of the cell the ant lands on at the end of a cycle
    (white is one, black is zero), read after any whole number of cycles
    since every instantiated program is a cycle-stable fixed point.  ``n ==
    1`` pads to a two-input table with the second input fixed to zero;
    ``n >= 3`` uses the same piecewise head with more bits, and every arity
    is exact and cycle-stable (see ``docs/a_painter_ant_generator.md``).
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

    def test_leaf_paint_uses_space_for_zero(self) -> None:
        """A zero leaf is left unpainted (space), a one leaf is painted P.

        The generator never paints a cell black (no ``p``), which is what
        keeps every instantiated program a monotone, cycle-stable fixed
        point.
        """
        template = a_painter_ant("0110")  # f(1,1)=0, f(0,0)=0, f(1,0)=1, f(0,1)=1
        assert " " in template  # zero leaves are spaces
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
        from esolangs.tools.boolean.a_painter_ant import _leaf_positions

        positions = _leaf_positions(4)
        assert len(positions) == 16
        assert len({(x, y) for x, y, _ in positions}) == 16  # all distinct

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

    def test_three_input_xor_works(self) -> None:
        """XOR3 is exact and cycle-stable on every input."""
        from itertools import product

        for bits in product([0, 1], repeat=3):
            table = "01101001"
            assert self._check(table, list(bits)) == int(
                table[bits[0] * 4 + bits[1] * 2 + bits[2]]
            ), f"XOR3 bits {bits}"

    def test_bad_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            a_painter_ant("011")

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


class TestWII2D:
    """Boolean generator for the no-input grid language WII2D."""

    def run_chain(self, tpl: str, bits: list[int]) -> str:
        """Instantiate the n-embedding chain template and run the interpreter."""
        from esolangs.interpreters.grid_based.wii2d import run as run_wii2d
        from esolangs.tools.boolean.examples import _fill_wii2d

        program = _fill_wii2d(tpl, bits)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            run_wii2d(program.splitlines(), io=IO())
        return buffer.getvalue()

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            ("01", 1),  # identity
            ("10", 1),  # NOT
            ("00", 1),  # constant zero
            ("11", 1),  # constant one
            ("0110", 2),  # XOR
            ("0001", 2),  # AND
            ("1110", 2),  # NAND
            ("11111110", 3),  # NAND3
            ("01101001", 3),  # XOR3
            ("0000000000000001", 4),  # AND4
            ("1111111100000000", 4),  # top half
        ],
    )
    def test_chain_truth_table(self, table: str, n: int) -> None:
        """Every instantiated input produces the truth-table result."""
        template = boolean.wii2d(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_chain(template, bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2])
    def test_chain_all_small_tables(self, n: int) -> None:
        """Every table up to two inputs works with the n-embedding chain."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = boolean.wii2d(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_chain(template, bits)
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    @pytest.mark.parametrize("n", [3, 4])
    def test_chain_sample_tables(self, n: int) -> None:
        """Sampled dense and structured tables at n = 3 and n = 4."""
        for table in (
            "01101001",  # XOR3
            "11101110",  # NOT-b0
            "10010110",  # XNOR3
            "1111111111111111",  # constant one
            "0000000100000010",  # a two-1 table
        ):
            if len(table) != 2**n:
                continue
            template = boolean.wii2d(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_chain(template, bits)
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_chain_embeds_each_input_once(self) -> None:
        """The n-embedding chain has each {Xi} placeholder exactly once."""
        import re

        for n in (1, 2, 3):
            template = boolean.wii2d(format(0, f"0{2**n}b"))
            xs = re.findall(r"\{X\d+\}", template)
            assert sorted(xs) == [f"{{X{i}}}" for i in range(n)], (n, xs)
            assert len(xs) == n, (n, xs)

    def test_apply_ignores_blank_cells(self) -> None:
        """A space is a no-op, so padding an op string cannot change it.

        The grid is a rectangle of blanks that the routes are painted into,
        so a route read back off it carries whatever spacing its row had --
        which must apply exactly as the unpadded route does.
        """
        from esolangs.tools.boolean.wii2d import _wii2d_apply

        for ops in ("+", "-", "*", "s", "+-", "*s"):
            want = _wii2d_apply(ops, 3)
            assert _wii2d_apply(f" {ops}", 3) == want, ops
            assert _wii2d_apply(f"{ops} ", 3) == want, ops
            assert _wii2d_apply(" ".join(ops), 3) == want, ops
        assert _wii2d_apply("   ", 7) == 7

    def test_chain_n2_closed_form(self) -> None:
        """Two-input tables use the closed form, not the search."""
        from esolangs.tools.boolean.wii2d import (
            _wii2d_apply,
            _wii2d_n2_closed_form,
        )

        for table_int in range(16):
            table = format(table_int, "04b")
            routes = _wii2d_n2_closed_form(table)
            # bit 0 is packed as -1 (zero) or 0 (one); each column decodes
            # with a single op
            assert routes[0] == ("-", "*"), table
            t = [int(c) for c in table]
            for b0 in (0, 1):
                for b1 in (0, 1):
                    value = _wii2d_apply(routes[1][b1], _wii2d_apply(routes[0][b0], 0))
                    assert value == t[b0 * 2 + b1], table
            # and the generated template uses the closed-form routes, laid
            # out with no blank column between the merge and what follows
            template = boolean.wii2d(table)
            assert template.startswith(">{X0}->{X1}"), table

    @pytest.mark.parametrize("n", [3, 4, 5, 6, 8])
    def test_chain_parity_closed_form(self, n: int) -> None:
        """Parity and its complement use the exact closed form for any arity."""
        from esolangs.tools.boolean.wii2d import (
            _wii2d_apply,
            _wii2d_parity_routes,
            _wii2d_symmetric_popcount_map,
        )

        for complement in (False, True):
            table = "".join(
                str((bin(c).count("1") % 2) ^ complement) for c in range(2**n)
            )
            popcount_map = _wii2d_symmetric_popcount_map(n, table)
            assert popcount_map is not None, table
            result = _wii2d_parity_routes(n, popcount_map)
            assert result is not None, table
            start, routes = result
            assert routes[1:] == [("", "-s")] * (n - 1), table
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                v = start
                for i in range(n):
                    v = _wii2d_apply(routes[i][bits[i]], v)
                assert str(v) == table[combo], (table, bits)

    def test_decode_realizes_every_small_pattern(self) -> None:
        """The decode primitive fits every 0/1 pattern on its domain.

        This is the whole construction's load-bearing claim: the chain half
        is fixed, so the generator reaches a table exactly when
        :func:`_wii2d_decode` fits the two columns.  Every pattern through
        eight points is checked here; the widest domain the generator asks
        for is sixteen (``n == 5``), covered by the sampled case below.
        """
        from esolangs.tools.boolean.wii2d import _wii2d_apply, _wii2d_decode

        for width in range(1, 9):
            for value in range(2**width):
                pattern = [(value >> (width - 1 - i)) & 1 for i in range(width)]
                ops = _wii2d_decode(pattern)
                assert ops is not None, (width, pattern)
                got = [_wii2d_apply(ops, x) for x in range(width)]
                assert got == pattern, (pattern, ops, got)

    @pytest.mark.slow
    def test_decode_realizes_sampled_wide_patterns(self) -> None:
        """The decode fits sampled 16-point patterns (the ``n == 5`` domain)."""
        import random

        from esolangs.tools.boolean.wii2d import _wii2d_apply, _wii2d_decode

        rng = random.Random(20260828)
        for _ in range(200):
            pattern = [rng.randint(0, 1) for _ in range(16)]
            ops = _wii2d_decode(pattern)
            assert ops is not None, pattern
            got = [_wii2d_apply(ops, x) for x in range(16)]
            assert got == pattern, (pattern, ops, got)

    def test_index_domain_guard_is_cost_not_capability(self) -> None:
        """The refusal is a size guard, and it charges the *real* domain.

        The generator rejects a dense non-symmetric table whose decode domain
        exceeds :data:`_WII2D_MAX_INDEX_DOMAIN` *without ever calling the
        decode*, so the refusal carries no evidence that the pattern is
        unreachable.  The arity the refusal starts at is derived from the
        constant, not pinned.

        What is charged is :func:`_wii2d_cost` -- the smaller of the
        ``2 ** (n - 1)`` worst case and the domain the chain actually leaves
        -- so the table has to be dense *and* unmerging to be refused.
        """
        import random

        from esolangs.tools.boolean.wii2d import (
            _WII2D_MAX_INDEX_DOMAIN,
            _wii2d_chain,
            _wii2d_cost,
            _wii2d_routes,
            _wii2d_symmetric_popcount_map,
        )

        # the first arity whose decode domain 2**(n-1) passes the guard
        n = (_WII2D_MAX_INDEX_DOMAIN).bit_length() + 1
        assert 2 ** (n - 1) > _WII2D_MAX_INDEX_DOMAIN
        assert 2 ** (n - 2) <= _WII2D_MAX_INDEX_DOMAIN

        # A dense non-symmetric table at that arity.  Pseudo-random rather
        # than patterned: a table with structure in it lets the chain merge,
        # which collapses the real domain below the guard and (correctly)
        # builds instead of being refused.
        rng = random.Random(20260904)
        while True:
            table = "".join(rng.choice("01") for _ in range(2**n))
            if _wii2d_symmetric_popcount_map(n, table) is None:
                break

        # the chain finds no merge, so the real domain is the worst case
        _chain, states = _wii2d_chain(n, table)
        assert _wii2d_cost(n, states) == 2 ** (n - 1)
        assert _wii2d_routes(n, table) is None

        with pytest.raises(ValueError, match="cost guard"):
            boolean.wii2d(table)

    def test_a_collapsing_chain_builds_past_the_dense_arity(self) -> None:
        """A structured table builds where a dense one of the same arity cannot.

        This is what charging the real domain buys.  The guard used to be
        compared against ``2 ** (n - 1)`` alone, which refused every table at
        an arity as soon as the *worst case* was too wide -- including tables
        whose chain merges down to a handful of points.  Both tables here sit
        at the arity the test above shows is refused.
        """
        from esolangs.tools.boolean.wii2d import (
            _WII2D_MAX_INDEX_DOMAIN,
            _wii2d_chain,
            _wii2d_real_domain,
            _wii2d_symmetric_popcount_map,
        )

        n = (_WII2D_MAX_INDEX_DOMAIN).bit_length() + 1

        # depends on three of the n inputs, so the chain merges the rest away
        table = "".join(
            str(((combo >> (n - 1)) ^ (combo >> (n - 3)) ^ (combo >> (n - 5))) & 1)
            for combo in range(2**n)
        )
        assert _wii2d_symmetric_popcount_map(n, table) is None

        _chain, states = _wii2d_chain(n, table)
        assert _wii2d_real_domain(states) <= _WII2D_MAX_INDEX_DOMAIN

        template = boolean.wii2d(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            assert self.run_chain(template, bits) == table[combo], f"inputs {bits}"

    def test_real_domain_guard_refuses_an_unmerging_chain(self) -> None:
        """A chain that finds no merge is refused on width, naming that bound.

        ``(b0|b1) & (b2|b3) & (b4|b5)`` at ``n == 7`` leaves a decode domain
        of 1025 -- far *above* the ``2 ** (n - 1)`` worst case, since Horner
        keeps doubling when no pair merges -- and that decode does not return
        in reasonable time.  :data:`_WII2D_MAX_REAL_DOMAIN` refuses it before
        the fold is attempted, so this test must never reach the decode.
        """
        from esolangs.tools.boolean.wii2d import (
            _WII2D_MAX_REAL_DOMAIN,
            _wii2d_chain,
            _wii2d_real_domain,
        )

        n = 7
        table = "".join(
            str(
                ((combo >> 6) | (combo >> 5))
                & ((combo >> 4) | (combo >> 3))
                & ((combo >> 2) | (combo >> 1))
                & 1
            )
            for combo in range(2**n)
        )

        _chain, states = _wii2d_chain(n, table)
        assert _wii2d_real_domain(states) > _WII2D_MAX_REAL_DOMAIN

        with pytest.raises(ValueError, match="width guard"):
            boolean.wii2d(table)

    @pytest.mark.slow
    def test_decode_folds_past_the_guard(self) -> None:
        """A 64-point decode -- the ``n == 7`` domain -- folds correctly.

        This is what makes the guard a cost policy rather than a wall: the
        construction is not out of reach at this width, it is merely
        expensive.  The pattern is fixed (not random) because decode time at
        this domain has a heavy tail; this one is a fast representative.
        """
        from esolangs.tools.boolean.wii2d import _wii2d_apply, _wii2d_decode

        pattern = [
            int(bit)
            for bit in "00110011001110001000010111111010"
            "00101111111010101001100110101001"
        ]
        assert len(pattern) == 64
        ops = _wii2d_decode(pattern)
        assert ops is not None
        assert [_wii2d_apply(ops, x) for x in range(64)] == pattern

    @pytest.mark.slow
    def test_chain_builds_and_runs_at_n7_when_the_guard_is_raised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Raising the guard yields a working ``n == 7`` program.

        The evidence gate for the "liftable, but costly" verdict: every one
        of the 128 input combinations is executed through the real
        interpreter and checked against the table.  The table is fixed so the
        build stays on the fast side of the decode's heavy tail.
        """
        from esolangs.tools.boolean.wii2d import _wii2d_symmetric_popcount_map

        module = importlib.import_module("esolangs.tools.boolean.wii2d")
        n = 7
        monkeypatch.setattr(module, "_WII2D_MAX_INDEX_DOMAIN", 2 ** (n - 1))

        table = (
            "1001101101110011101111111100000100010000001110100111111110001011"
            "0010100001000011100000001010010001100010001001011101101110101111"
        )
        assert len(table) == 2**n
        assert _wii2d_symmetric_popcount_map(n, table) is None

        template = module.wii2d(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_chain(template, bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    def test_decode_takes_one_candidate_and_never_backtracks(self) -> None:
        """The decode is a single pass: the head candidate, every step.

        This is the property that makes it a construction rather than a
        search, so it is pinned directly.  Wrapping ``_wii2d_folds`` to hand
        back *only* its first candidate cannot change any emitted op string,
        because the decode never looks at the others.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.wii2d")
        from esolangs.tools.boolean.wii2d import (
            _wii2d_apply,
            _wii2d_decode,
            _wii2d_folds,
        )

        patterns = [
            [0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 0, 0, 1, 0, 1],
            [0, 1] * 8,
            [1, 1, 0, 0, 1, 0, 1, 0],
        ]
        before = [_wii2d_decode(list(p)) for p in patterns]

        head_only = _wii2d_folds
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                module,
                "_wii2d_folds",
                lambda values, bits: head_only(values, bits)[:1],
            )
            after = [_wii2d_decode(list(p)) for p in patterns]

        assert after == before
        for pattern, ops in zip(patterns, before, strict=True):
            assert ops is not None
            assert [_wii2d_apply(ops, x) for x in range(len(pattern))] == pattern

    def test_decode_is_exhaustive_over_the_widest_shipped_domain(self) -> None:
        """Every eight-point pattern decodes under the single-candidate rule.

        ``D == 8`` is exhaustive here to keep the test quick; the same sweep
        run over all 65536 patterns at ``D == 16`` -- the widest domain the
        general path asks for -- also passes, which is what licenses the
        claim that the rule needs no beam.
        """
        import itertools

        from esolangs.tools.boolean.wii2d import _wii2d_apply, _wii2d_decode

        for bits in itertools.product([0, 1], repeat=8):
            pattern = list(bits)
            ops = _wii2d_decode(pattern)
            assert ops is not None, pattern
            assert [_wii2d_apply(ops, x) for x in range(8)] == pattern

    def test_decode_constant_pattern_is_a_single_digit(self) -> None:
        """A constant column needs no folding at all, just a digit."""
        from esolangs.tools.boolean.wii2d import _wii2d_decode

        assert _wii2d_decode([0, 0, 0, 0]) == "0"
        assert _wii2d_decode([1, 1, 1, 1]) == "1"

    def test_decode_centre_cap_has_a_constructed_miss(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A fixed fold-centre cap cannot make the greedy decoder total.

        For every even cap ``K``, ``0 1**K 0 1`` defeats both first-pass
        compressions and every fold at a centre at most ``K``.  A doubled
        fold centred at ``c`` sees the opposite-bit pair ``(0, c)``; an
        undoubled one sees ``(0, 2c)`` up to ``K / 2`` and
        ``(K + 1, 2c - K - 1)`` above it.  So every candidate merges unlike
        bits.  Raising the cap by one exposes the all-zero pair ``(0, K+1)``,
        which is the positive control that the miss is the cap rather than a
        defect in the fold algebra.
        """
        import importlib

        from esolangs.tools.boolean.wii2d import _wii2d_apply, _wii2d_decode

        module = importlib.import_module("esolangs.tools.boolean.wii2d")
        cap = 4
        pattern = [0, *([1] * cap), 0, 1]

        monkeypatch.setattr(module, "_WII2D_MAX_CENTRE", cap)
        assert _wii2d_decode(pattern) is None

        monkeypatch.setattr(module, "_WII2D_MAX_CENTRE", cap + 1)
        ops = _wii2d_decode(pattern)
        assert ops is not None
        assert [_wii2d_apply(ops, value) for value in range(len(pattern))] == pattern

    def test_threshold_reads_out_two_live_values(self) -> None:
        """The tail turns the last two values into their bits, either way round."""
        from esolangs.tools.boolean.wii2d import _wii2d_apply, _wii2d_threshold

        rising = _wii2d_threshold({3: 0, 9: 1})
        assert _wii2d_apply(rising, 3) == 0
        assert _wii2d_apply(rising, 9) == 1
        falling = _wii2d_threshold({3: 1, 9: 0})
        assert _wii2d_apply(falling, 3) == 1
        assert _wii2d_apply(falling, 9) == 0
        assert _wii2d_threshold({7: 1}) == "1"

    def test_points_rejects_a_collision_needing_both_bits(self) -> None:
        """Two inputs on one value needing different bits is unrecoverable."""
        from esolangs.tools.boolean.wii2d import _wii2d_points

        assert _wii2d_points([0, 1, 2], [0, 1, 0]) == {0: 0, 1: 1, 2: 0}
        assert _wii2d_points([0, 1, 1], [0, 1, 0]) is None

    def test_compress_steers_with_an_increment(self) -> None:
        """When a plain halving would collide, ``+`` re-pairs the neighbours.

        A bare ``/`` sends both 2 and 3 to 1, which loses the distinction
        the two bits need; incrementing first splits them to 1 and 2, so
        compression makes progress instead of stalling.
        """
        from esolangs.tools.boolean.wii2d import _wii2d_apply, _wii2d_compress

        values, ops = _wii2d_compress([2, 3], [0, 1], "")
        # the two inputs stay on distinct values ...
        assert values[0] != values[1]
        # ... and the ops actually produce those values
        assert [_wii2d_apply(ops, v) for v in (2, 3)] == values
        assert "+" in ops

    def test_compress_stops_when_halving_stops_moving(self) -> None:
        """Values a halving cannot separate end the compression.

        ``0`` and ``-1`` are both fixpoints of ``(v + shift) // 2``, so
        neither shift makes progress and there is nothing further to try.
        Returning the values as they stand lets the caller decide; looping
        on them would not terminate.
        """
        from esolangs.tools.boolean.wii2d import _wii2d_compress

        values, ops = _wii2d_compress([-1, -1], [1, 1], "")
        assert values == [-1, -1]
        assert ops == "", "a stalled compression emits no ops"

    def test_a_fold_that_merges_nothing_is_not_offered(self) -> None:
        """A centre that leaves every point distinct buys no progress.

        The fold exists to shrink the live set; one that returns as many
        values as it was given has cost the ops for nothing, so it is
        dropped rather than ranked.
        """
        from esolangs.tools.boolean.wii2d import _wii2d_folds

        assert _wii2d_folds([0, 1], [0, 1]) == []
        # A state that already collides has no live map at all, so neither
        # the plain nor the doubled scaling offers a fold.
        assert _wii2d_folds([2, 2], [0, 1]) == []

    def test_a_centre_too_far_out_to_spell_is_skipped(self) -> None:
        """A midpoint past the cap is correct but too wide for the grid.

        The offset is spelled out in the program, so a centre far from the
        origin costs more characters than the grid has room for.  The two
        states here are the same shape -- two points needing one bit and a
        third needing the other -- and differ only in how far from zero
        they sit, so the empty result is the cap and not the pattern.
        """
        from esolangs.tools.boolean.wii2d import _WII2D_MAX_CENTRE, _wii2d_folds

        near = _wii2d_folds([0, 4, 10], [1, 1, 0])
        assert near, "the positive control must fold"

        centre = (20000 + 20004) // 2
        assert centre > _WII2D_MAX_CENTRE
        assert _wii2d_folds([20000, 20004, 20010], [1, 1, 0]) == []

    def test_the_beam_search_gives_up_when_no_fold_survives(self) -> None:
        """With every fold rejected the search has nowhere to go.

        Reaching this naturally needs a pattern no beam width can decode,
        and none is known -- every pattern tried up to sixteen inputs
        decodes.  Emptying the fold list is the same dead end seen from
        inside, and it pins that the answer is ``None`` rather than a
        wrong decode.
        """
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.boolean.wii2d")
        from esolangs.tools.boolean.wii2d import _wii2d_decode

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_wii2d_folds", lambda *_: [])
            assert _wii2d_decode([0, 1, 1, 0]) is None

    def test_folds_that_never_shrink_run_the_loop_out(self) -> None:
        """A fold that returns its own state exhausts the iteration bound.

        Real folds merge at least one pair, so the live count strictly drops
        and the loop is far shorter than its bound.  A fold that shrinks
        nothing is the pathological case the bound exists for: it must stop
        and answer ``None`` rather than spin.
        """
        import importlib

        # The package re-exports the generator under the submodule's own
        # name, so import the module explicitly rather than by attribute.
        module = importlib.import_module("esolangs.tools.boolean.wii2d")
        from esolangs.tools.boolean.wii2d import _wii2d_decode

        def stuck(
            values: list[int], _bits: list[int]
        ) -> list[tuple[int, int, int, str, list[int]]]:
            return [(max(values), len(set(values)), 1, "+", list(values))]

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_wii2d_folds", stuck)
            # four distinct live values, so the two-value exit never fires
            assert _wii2d_decode([0, 1, 1, 0, 1, 0, 0, 1]) is None

        # A fold that collides two inputs needing different bits leaves a
        # state with no live map at all; that is a dead end, not a decode.
        def collides(
            _values: list[int], _bits: list[int]
        ) -> list[tuple[int, int, int, str, list[int]]]:
            return [(2, 1, 1, "", [2, 2, 2, 2])]

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_wii2d_folds", collides)
            assert _wii2d_decode([0, 1, 1, 0]) is None

    def test_chain_is_a_junction_chain_then_a_decode(self) -> None:
        """The constructed routes have the shape the docstring claims.

        The chain junctions are no longer a fixed Horner step: each level
        takes the first legal pair from ``_WII2D_JUNCTIONS``, so what is
        pinned here is the *contract* -- one junction per input, drawn from
        the catalogue, and the whole chain evaluating the table -- rather
        than the particular pairs a given table happens to select.
        """
        from esolangs.tools.boolean.wii2d import (
            _WII2D_JUNCTIONS,
            _wii2d_apply,
            _wii2d_routes,
        )

        n = 4
        # not parity and not symmetric, so neither closed form intercepts it
        table = "0001011001101011"
        result = _wii2d_routes(n, table)
        assert result is not None
        start, routes = result
        assert start == 0
        assert len(routes) == n
        # every junction but the last comes from the catalogue
        for pair in routes[:-1]:
            assert pair in _WII2D_JUNCTIONS
        # and the chain plus decode reproduces the table
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            value = start
            for i, bit in enumerate(bits):
                value = _wii2d_apply(routes[i][bit], value)
            assert value == int(table[combo]), f"inputs {bits}"

    def test_horner_is_the_catalogue_fallback(self) -> None:
        """Horner ends the catalogue, and is legal at every level.

        The chain is total because ``('*', '*+')`` never collides two
        distinct cofactors -- the children differ in parity -- so the walk
        always has a legal pair to take.  With every merging pair removed the
        chain must therefore still build, and rebuild the plain index.
        """
        import importlib

        module = importlib.import_module("esolangs.tools.boolean.wii2d")
        from esolangs.tools.boolean.wii2d import _WII2D_JUNCTIONS, _wii2d_chain

        assert _WII2D_JUNCTIONS[-1] == ("*", "*+")

        n = 4
        table = "0001011001101011"
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_WII2D_JUNCTIONS", (("*", "*+"),))
            routes, states = _wii2d_chain(n, table)
        assert routes == [("*", "*+")] * (n - 1)
        # Horner merges nothing, so the values are the dense index range
        assert sorted(value for _, value in states) == list(range(2 ** (n - 1)))

    def test_symmetric_tables_use_a_popcount_chain(self) -> None:
        """A symmetric table decodes over ``n`` points, not ``2 ** (n - 1)``.

        Majority-of-10 is the case the index chain cannot help with -- its
        decode domain would be 512 points -- so this pins that symmetric
        tables take the popcount chain instead, and that the result is
        exact on every one of the 1024 inputs.
        """
        import itertools

        from esolangs.tools.boolean.wii2d import _wii2d_apply, _wii2d_routes

        n = 10
        table = "".join(
            "1" if bin(combo).count("1") > n // 2 else "0" for combo in range(2**n)
        )
        result = _wii2d_routes(n, table)
        assert result is not None
        start, routes = result
        assert routes[:-1] == [("", "+")] * (n - 1)
        for combo, bits in enumerate(itertools.product((0, 1), repeat=n)):
            acc = start
            for i, bit in enumerate(bits):
                acc = _wii2d_apply(routes[i][bit], acc)
            assert acc == int(table[combo]), (bits, acc)

    def test_symmetric_non_monotone_table_is_reachable(self) -> None:
        """An exactly-k-of-n table is symmetric but not monotone, and fits."""
        import itertools

        from esolangs.tools.boolean.wii2d import _wii2d_apply, _wii2d_routes

        n, k = 6, 3
        table = "".join(
            "1" if bin(combo).count("1") == k else "0" for combo in range(2**n)
        )
        result = _wii2d_routes(n, table)
        assert result is not None
        start, routes = result
        for combo, bits in enumerate(itertools.product((0, 1), repeat=n)):
            acc = start
            for i, bit in enumerate(bits):
                acc = _wii2d_apply(routes[i][bit], acc)
            assert acc == int(table[combo]), (bits, acc)

    def test_routes_reproduce_every_table_at_three_inputs(self) -> None:
        """Constructed routes evaluate to the table for all 256 three-bit tables."""
        import itertools

        from esolangs.tools.boolean.wii2d import _wii2d_apply, _wii2d_routes

        n = 3
        for value in range(2 ** (2**n)):
            table = format(value, f"0{2**n}b")
            result = _wii2d_routes(n, table)
            assert result is not None, table
            start, routes = result
            for combo, bits in enumerate(itertools.product((0, 1), repeat=n)):
                acc = start
                for i, bit in enumerate(bits):
                    acc = _wii2d_apply(routes[i][bit], acc)
                assert acc == int(table[combo]), (table, bits, acc)

    def test_routes_are_deterministic(self) -> None:
        """The construction is a pure function of the table, not of the host."""
        from esolangs.tools.boolean.wii2d import _wii2d_routes

        table = "0001011001101001"
        assert _wii2d_routes(4, table) == _wii2d_routes(4, table)

    def test_a_dense_seven_input_table_builds_and_runs(self) -> None:
        """A dense ``n == 7`` table builds, and every one of its 128 fills runs.

        This table used to be the generator's refusal case: the guard was 32
        and fired on the ``2 ** (n - 1) == 64`` worst case *before* the chain
        was walked, so it never carried evidence that anything failed.  It
        does not fail.  The guard is now 64, and the price is width -- 25
        random tables at this arity measured a median 2776 characters and 65
        ms, against 758 and 7.8 ms at ``n == 6``.

        The execution gate is the point of the test: a size measurement alone
        would not show that the emitted program still computes the table.
        """
        table = (
            "0011001100111000100001011111101000101111111010101001100110101001"
            "1100011100100000111001110111101101111101101001111110001111101011"
        )
        assert len(table) == 128  # n == 7

        from esolangs.tools.boolean.wii2d import _wii2d_symmetric_popcount_map

        # not symmetric, so this is the general path rather than the popcount
        # chain that lets symmetric tables off cheaply
        assert _wii2d_symmetric_popcount_map(7, table) is None

        template = boolean.wii2d(table)
        for combo in range(128):
            bits = [(combo >> (6 - i)) & 1 for i in range(7)]
            assert self.run_chain(template, bits) == table[combo], f"inputs {bits}"

    def test_a_branch_that_will_not_decode_refuses_the_chain(self) -> None:
        """Both halves of the index chain have to decode, or there is no route.

        The chain splits the table into the even and odd rows and decodes
        each as its own pattern; a half that cannot be decoded leaves the
        junction with nothing to branch on.  Every pattern tried decodes,
        so the refusal is reached by taking the decoder away.
        """
        module = importlib.import_module("esolangs.tools.boolean.wii2d")
        from esolangs.tools.boolean.wii2d import _wii2d_routes

        # n == 2 has a closed form and a symmetric table has the popcount
        # chain, neither of which consults the branch decoder -- so this
        # takes a non-symmetric table at the smallest arity that does.
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_wii2d_decode", lambda *_a, **_k: None)
            assert _wii2d_routes(3, "00010111") is None

    def test_wii2d_raises_when_the_construction_finds_no_route(self) -> None:
        """``wii2d`` surfaces a construction failure as a ``ValueError``."""
        from esolangs.tools.boolean import parameterized

        wii2d_mod = importlib.import_module("esolangs.tools.boolean.wii2d")

        with (
            patch.object(wii2d_mod, "_wii2d_routes", return_value=None),
            pytest.raises(ValueError, match="no route"),
        ):
            parameterized.wii2d("0110")

    def test_layout_embeds_a_nonzero_start_digit(self) -> None:
        """A nonzero ``start`` writes an initial digit before the chain runs.

        The construction happens not to need a nonzero start for the small
        tables sampled elsewhere in this file, so this drives
        :func:`_wii2d_layout` directly with one and confirms the produced
        template actually runs correctly through the real interpreter.
        """
        from esolangs.tools.boolean.wii2d import _wii2d_layout

        template = "\n".join(_wii2d_layout(1, 5, [("", "+")]))
        for bit, expected in ((0, "5"), (1, "6")):
            assert self.run_chain(template, [bit]) == expected


class TestCircuitDiagram:
    """The Circuit Diagram generator (a real gate network, input-reading).

    Circuit Diagram draws boolean circuits, so a truth table is its native
    idiom and the generator is a sum of minterms rather than a decision
    tree: ``n`` input lines, a bus per literal, an ``a`` chain per minterm,
    an ``o`` chain combining them, and a ``:`` that prints the answer.

    Every assertion here replays the generated program through the real
    interpreter over the table's *whole* input space, which is what makes
    the layout trustworthy: a wire that merges into its neighbour or a gate
    fed a generation late shows up as a wrong bit, and no static check on
    the ASCII would catch either.
    """

    @staticmethod
    def run_table(table: str) -> str:
        """Return the generated program's output for every input, in order."""
        from esolangs.interpreters.grid_based.circuit_diagram import run
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.boolean.circuit_diagram import circuit_diagram

        n = len(table).bit_length() - 1
        program = circuit_diagram(table).split("\n")
        results = []
        for index in range(len(table)):
            bits = format(index, f"0{n}b")
            stdin = "".join(f"{bit}\n" for bit in bits)
            io = ScriptedIO(stdin)
            run(program, io)
            results.append(io.getvalue())
        return "".join(results)

    @pytest.mark.parametrize("table", [format(i, "04b") for i in range(16)])
    def test_every_two_input_table(self, table: str) -> None:
        """All sixteen two-input functions, each over all four inputs."""
        assert self.run_table(table) == table

    @pytest.mark.parametrize("table", ["01", "10", "00", "11"])
    def test_every_one_input_table(self, table: str) -> None:
        assert self.run_table(table) == table

    @pytest.mark.parametrize(
        "table",
        ["00010111", "01101001", "11110000", "00000000", "11111111"],
    )
    def test_three_input_tables(self, table: str) -> None:
        """Majority, parity, a projection, and both constants."""
        assert self.run_table(table) == table

    @pytest.mark.parametrize(
        ("table", "tildes"),
        [
            ("0001", 0),  # AND: every minterm bit is 1, so no complement
            ("01", 0),  # identity: likewise
            ("10", 1),  # NOT: its one minterm selects the complement
            ("0110", 2),  # XOR: both inputs appear negated and plain
        ],
    )
    def test_only_needed_complements_are_built(self, table: str, tildes: int) -> None:
        """A ``~`` is drawn only when some minterm selects that complement.

        Building all ``2n`` literals unconditionally left a gate driving a
        bus nothing read, plus the tap and the run out to it -- for AND that
        was more than half the drawing.
        """
        from esolangs.tools.boolean.circuit_diagram import circuit_diagram

        assert circuit_diagram(table).count("~") == tildes

    def test_a_dense_table_is_drawn_as_its_complement(self) -> None:
        """More ones than zeros costs less built from the zero rows.

        A chain is a gate per literal plus the runs feeding it, so the
        saving is far larger than the one ``~`` that inverts the result:
        NAND3 selects seven rows drawn directly and one complemented.
        """
        from esolangs.tools.boolean.circuit_diagram import circuit_diagram

        dense = circuit_diagram("11111110")  # NAND3: seven ones
        sparse = circuit_diagram("00000001")  # its complement: one
        assert len(dense) < 2 * len(sparse)
        # both compute their own table, whichever way they were drawn
        assert self.run_table("11111110") == "11111110"
        assert self.run_table("00000001") == "00000001"

    def test_a_constant_table_is_never_complemented(self) -> None:
        """It is already one gate, so complementing only swaps the glyph.

        An all-ones table is the trap: complementing leaves no minterms at
        all, which is the all-zeros shape, so the result would print the
        wrong constant unless the table is excluded outright.
        """
        assert self.run_table("1111") == "1111"
        assert self.run_table("0000") == "0000"

    def test_four_input_primality(self) -> None:
        """The same function the wiki's own worked example computes.

        The wiki's prime tester is a hand-drawn product of sums; this is the
        generator's sum of minterms for the same table, so the two agree on
        every one of the sixteen inputs by different constructions.
        """
        primes = {n for n in range(2, 16) if all(n % d for d in range(2, n))}
        table = "".join("1" if n in primes else "0" for n in range(16))
        assert self.run_table(table) == table

    def test_each_run_prints_exactly_one_bit(self) -> None:
        """The output wire is live for exactly one generation.

        A ``:`` prints in every generation its wire carries a value, so a
        second driver on any wiring -- or two wirings merged by adjacent
        junctions -- would show up as extra characters even when the value
        happens to be right.
        """
        from esolangs.interpreters.grid_based.circuit_diagram import run
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.boolean.circuit_diagram import circuit_diagram

        for table in ("0001", "0110", "00010111"):
            n = len(table).bit_length() - 1
            program = circuit_diagram(table).split("\n")
            for index in range(len(table)):
                stdin = "".join(f"{b}\n" for b in format(index, f"0{n}b"))
                io = ScriptedIO(stdin)
                run(program, io)
                assert len(io.getvalue()) == 1

    def test_input_lines_start_with_a_dash(self) -> None:
        """Each bit arrives on its own line, which the spec makes an input."""
        from esolangs.tools.boolean.circuit_diagram import circuit_diagram

        rows = circuit_diagram("00010111").split("\n")
        starts = [row for row in rows if row.startswith("-")]
        assert len(starts) == 3

    def test_a_malformed_table_is_rejected(self) -> None:
        from esolangs.tools.boolean.circuit_diagram import circuit_diagram

        with pytest.raises(ValueError, match="power-of-two"):
            circuit_diagram("010")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            circuit_diagram("012x")
