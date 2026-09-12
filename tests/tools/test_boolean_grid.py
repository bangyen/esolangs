r"""Unit tests for the grid-based boolean generators."""

import hashlib
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
    r"""Render after exactly ``passes`` whole cycles, stepped by hand."""
    machine = _APAMachine(program)
    span = len(machine.prog)
    for _ in range(passes * span):
        machine.step()
    return machine.render()


# 2.0s over 45 tests: runs the.
@pytest.mark.medium
class TestAPainterAnt:
    r"""The A Painter Ant generator (a no-I/O grid language, parameterized."""

    _MOVE: ClassVar[dict[str, tuple[int, int]]] = {
        "n": (0, -1),
        "e": (1, 0),
        "s": (0, 1),
        "w": (-1, 0),
    }

    @staticmethod
    def _landing_after(program: str, cycles: int = 6) -> int:
        r"""Landing cell colour (1 white, 0 black) after ``cycles`` cycles."""
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
        r"""``run()``'s auto-detected render agrees with a render pinned to ten."""
        from esolangs.interpreters.io import ScriptedIO

        io = ScriptedIO()
        run_a_painter_ant(program, io)
        return io.getvalue() == _render_after_passes(program, 10)

    @classmethod
    def _check(cls, table: str, bits: list[int]) -> int:
        program = _instantiate_apa(a_painter_ant(table), bits)
        assert cls._cycle_stable(program), f"{table} {bits}: not cycle-stable"
        return cls._landing_after(program)

    @pytest.mark.slow  # 1.2s: builds and runs all.
    def test_all_two_input_functions(self) -> None:
        r"""Every two-input table is exact and cycle-stable for every input."""
        for value in range(16):
            table = format(value, "04b")
            for row in range(4):
                bits = [(row >> 1) & 1, row & 1]
                assert self._check(table, bits) == int(table[row]), (
                    f"{table} bits {bits}"
                )

    def test_xor(self) -> None:
        r"""XOR (0110) is one of the expressible tables."""
        assert self._check("0110", [0, 0]) == 0
        assert self._check("0110", [0, 1]) == 1
        assert self._check("0110", [1, 0]) == 1
        assert self._check("0110", [1, 1]) == 0

    def test_nand(self) -> None:
        r"""NAND (1110) is expressible."""
        assert self._check("1110", [0, 0]) == 1
        assert self._check("1110", [1, 1]) == 0

    def test_constant_tables(self) -> None:
        r"""Constant zero and one are expressible."""
        assert self._check("0000", [0, 0]) == 0
        assert self._check("0000", [1, 1]) == 0
        assert self._check("1111", [0, 0]) == 1
        assert self._check("1111", [1, 1]) == 1

    def test_template_has_input_placeholders(self) -> None:
        r"""The template carries {X0} and {X1}, not hardcoded bits."""
        template = a_painter_ant("0110")
        assert "{X0}" in template
        assert "{X1}" in template

    def test_leaf_paint_uses_space_for_zero(self) -> None:
        r"""A zero leaf is left unpainted (space), a one leaf is painted P."""
        template = a_painter_ant("0110")  # f(1,1)=0, f(0,0)=0, f(1,0)=1,.
        assert " " in template  # zero leaves are spaces.
        # no paint-black anywhere in.
        program = _instantiate_apa(template, [1, 1])
        assert "p" not in program

    def test_all_one_input_functions(self) -> None:
        r"""Every one-input table is exact and cycle-stable for both inputs."""
        for value in range(4):
            table = format(value, "02b")
            for bit in [0, 1]:
                assert self._check(table, [bit]) == int(table[bit]), (
                    f"table {table} bit {bit}"
                )

    def test_instantiate_one_bit_fills_single_placeholder(self) -> None:
        r"""An n == 1 template carries only {X0}, filled per bit."""
        template = a_painter_ant("01")  # f(0)=0, f(1)=1.
        assert "{X0}" in template
        assert "{X1}" not in template
        assert _instantiate_apa(template, [1]) == template.replace("{X0}", "WWwWWEEe")
        assert _instantiate_apa(template, [0]) == template.replace("{X0}", "NENEESWw")

    def test_three_input_works(self) -> None:
        r"""AND3 is exact and cycle-stable on every input."""
        from itertools import product

        for bits in product([0, 1], repeat=3):
            table = "00000001"
            assert self._check(table, list(bits)) == int(
                table[bits[0] * 4 + bits[1] * 2 + bits[2]]
            ), f"AND3 bits {bits}"

    def test_four_input_head_works(self) -> None:
        r"""The head's leaf layout generalizes past three inputs."""
        from esolangs.tools.boolean.a_painter_ant import _leaf_positions

        positions = _leaf_positions(4)
        assert len(positions) == 16
        assert len({(x, y) for x, y, _ in positions}) == 16  # all distinct.

    def test_leaf_coordinates_agree_with_the_moves_that_walk_them(self) -> None:
        r"""``_leaf_positions`` is the mirror of what ``_bit_move`` emits."""
        from esolangs.tools.boolean.a_painter_ant import _bit_move, _leaf_positions

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
        r"""Each bit contributes ``+-2**(n-k)`` on the axis its index picks."""
        from esolangs.tools.boolean.a_painter_ant import _leaf_positions

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
        r"""The generator handles n == 4 and n == 5, exact and cycle-stable."""
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
        r"""XOR3 is exact and cycle-stable on every input."""
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
        r"""{X0} fills nnnn/ssss (the 2^(n-i)=4 weight) and {X1} fills the E/W."""
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
    r"""The A Painter Ant step tracer and cycle-stability checker."""

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
        assert outcome.grid[(0, -1)] == 0  # p repaints the white cell.
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

        assert run("nP", 1).landing_colour() == 1  # (0,-1) was painted white.
        assert run("n", 1).landing_colour() == 0  # (0,-1) is still black.

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

        assert not cycle_stable("nPn")  # each cycle paints one cell.

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

        divergence = first_divergence("nPn")  # cycle 2 moves to (0,-3),.
        assert divergence is not None
        assert divergence.index == 0
        assert divergence.command == "n"
        assert divergence.position == (0, -3)
        assert divergence.step1.position == (0, -1)
        assert divergence.step2.position == (0, -3)

    def test_first_divergence_pins_a_paint_break(self) -> None:
        from tests.tools.a_painter_ant_trace import first_divergence

        divergence = first_divergence("Pn")  # cycle 2 paints the black.
        assert divergence is not None
        assert divergence.index == 0
        assert divergence.command == "P"
        assert divergence.step1.position == (0, 0)
        assert divergence.step2.position == (0, -1)

    def test_first_divergence_pins_a_changed_answer(self) -> None:
        from tests.tools.a_painter_ant_trace import first_divergence

        # cycle 1 lands white on.
        divergence = first_divergence("nPnPsS")
        assert divergence is not None
        assert divergence.index == 5
        assert divergence.command == "S"
        assert divergence.step1.position == (0, -1)
        assert divergence.step2.position == (0, 0)

    def test_first_divergence_pins_a_drifting_dance(self) -> None:
        from tests.tools.a_painter_ant_trace import first_divergence

        # cycle 2 lands on (0,0).
        # is not a fixed point and.
        divergence = first_divergence("NPsP")
        assert divergence is not None
        assert divergence.index == 0
        assert divergence.command == "N"
        assert divergence.step1.action == "moved"
        assert divergence.step2.action == "blocked"


class TestWII2D:
    r"""Boolean generator for the no-input grid language WII2D."""

    def run_chain(self, tpl: str, bits: list[int]) -> str:
        r"""Instantiate the n-embedding chain template and run the interpreter."""
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
            ("01", 1),  # identity.
            ("10", 1),  # NOT.
            ("00", 1),  # constant zero.
            ("11", 1),  # constant one.
            ("0110", 2),  # XOR.
            ("0001", 2),  # AND.
            ("1110", 2),  # NAND.
            ("11111110", 3),  # NAND3.
            ("01101001", 3),  # XOR3.
            ("0000000000000001", 4),  # AND4.
            ("1111111100000000", 4),  # top half.
        ],
    )
    def test_chain_truth_table(self, table: str, n: int) -> None:
        r"""Every instantiated input produces the truth-table result."""
        template = boolean.wii2d(table)
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            got = self.run_chain(template, bits)
            assert got == str(int(table[combo])), f"inputs {bits}"

    @pytest.mark.parametrize("n", [1, 2])
    def test_chain_all_small_tables(self, n: int) -> None:
        r"""Every table up to two inputs works with the n-embedding chain."""
        for table_int in range(2 ** (2**n)):
            table = format(table_int, f"0{2**n}b")
            template = boolean.wii2d(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_chain(template, bits)
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    @pytest.mark.parametrize("n", [3, 4])
    def test_chain_sample_tables(self, n: int) -> None:
        r"""Sampled dense and structured tables at n = 3 and n = 4."""
        for table in (
            "01101001",  # XOR3.
            "11101110",  # NOT-b0.
            "10010110",  # XNOR3.
            "1111111111111111",  # constant one.
            "0000000100000010",  # a two-1 table.
        ):
            if len(table) != 2**n:
                continue
            template = boolean.wii2d(table)
            for combo in range(2**n):
                bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
                got = self.run_chain(template, bits)
                assert got == str(int(table[combo])), f"{table} inputs {bits}"

    def test_chain_embeds_each_input_once(self) -> None:
        r"""The n-embedding chain has each {Xi} placeholder exactly once."""
        import re

        for n in (1, 2, 3):
            template = boolean.wii2d(format(0, f"0{2**n}b"))
            xs = re.findall(r"\{X\d+\}", template)
            assert sorted(xs) == [f"{{X{i}}}" for i in range(n)], (n, xs)
            assert len(xs) == n, (n, xs)

    def test_apply_ignores_blank_cells(self) -> None:
        r"""A space is a no-op, so padding an op string cannot change it."""
        from esolangs.tools.boolean.wii2d import _wii2d_apply

        for ops in ("+", "-", "*", "s", "+-", "*s"):
            want = _wii2d_apply(ops, 3)
            assert _wii2d_apply(f" {ops}", 3) == want, ops
            assert _wii2d_apply(f"{ops} ", 3) == want, ops
            assert _wii2d_apply(" ".join(ops), 3) == want, ops
        assert _wii2d_apply("   ", 7) == 7

    def test_chain_n2_closed_form(self) -> None:
        r"""Two-input tables use the closed form, not the search."""
        from esolangs.tools.boolean.wii2d import (
            _wii2d_apply,
            _wii2d_n2_closed_form,
        )

        for table_int in range(16):
            table = format(table_int, "04b")
            routes = _wii2d_n2_closed_form(table)
            # bit 0 is packed as -1 (zero).
            # with a single op.
            assert routes[0] == ("-", "*"), table
            t = [int(c) for c in table]
            for b0 in (0, 1):
                for b1 in (0, 1):
                    value = _wii2d_apply(routes[1][b1], _wii2d_apply(routes[0][b0], 0))
                    assert value == t[b0 * 2 + b1], table
            # and the generated template.
            # out with no blank column.
            template = boolean.wii2d(table)
            assert template.startswith(">{X0}->{X1}"), table

    @pytest.mark.parametrize("n", [3, 4, 5, 6, 8])
    def test_chain_parity_closed_form(self, n: int) -> None:
        r"""Parity and its complement use the exact closed form for any arity."""
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
        r"""The decode primitive fits every 0/1 pattern on its domain."""
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
        r"""The decode fits sampled 16-point patterns (the ``n == 5`` domain)."""
        import random

        from esolangs.tools.boolean.wii2d import _wii2d_apply, _wii2d_decode

        rng = random.Random(20260828)
        for _ in range(200):
            pattern = [rng.randint(0, 1) for _ in range(16)]
            ops = _wii2d_decode(pattern)
            assert ops is not None, pattern
            got = [_wii2d_apply(ops, x) for x in range(16)]
            assert got == pattern, (pattern, ops, got)

    @pytest.mark.slow  # ~21s at n == 9: a 1.1s build,.
    def test_a_dense_table_at_the_widest_admitted_domain_runs(self) -> None:
        r"""The arity the guard now admits is executed, not just rendered."""
        from esolangs.tools.boolean.wii2d import _WII2D_MAX_INDEX_DOMAIN

        # The widest arity the guard.
        n = (_WII2D_MAX_INDEX_DOMAIN).bit_length()
        assert 2 ** (n - 1) <= _WII2D_MAX_INDEX_DOMAIN
        digest = hashlib.sha256(f"dense:{n}".encode()).digest()
        bits: list[str] = []
        block = 0
        while len(bits) < 2**n:
            digest = hashlib.sha256(digest + bytes([block & 255])).digest()
            bits.extend(str(byte & 1) for byte in digest)
            block += 1
        table = "".join(bits[: 2**n])
        template = boolean.wii2d(table)
        for combo in range(2**n):
            row = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            assert self.run_chain(template, row) == table[combo], f"row {combo}"

    def test_index_domain_guard_is_cost_not_capability(self) -> None:
        r"""The refusal is a size guard, and it charges the *real* domain."""
        import random

        from esolangs.tools.boolean.wii2d import (
            _WII2D_MAX_INDEX_DOMAIN,
            _wii2d_chain,
            _wii2d_cost,
            _wii2d_routes,
            _wii2d_symmetric_popcount_map,
        )

        # the first arity whose decode.
        n = (_WII2D_MAX_INDEX_DOMAIN).bit_length() + 1
        assert 2 ** (n - 1) > _WII2D_MAX_INDEX_DOMAIN
        assert 2 ** (n - 2) <= _WII2D_MAX_INDEX_DOMAIN

        # A dense non-symmetric table.
        # than patterned: a table with.
        # which collapses the real.
        # builds instead of being.
        rng = random.Random(20260904)
        while True:
            table = "".join(rng.choice("01") for _ in range(2**n))
            if _wii2d_symmetric_popcount_map(n, table) is None:
                break

        # the chain finds no merge, so.
        _chain, states = _wii2d_chain(n, table)
        assert _wii2d_cost(n, states) == 2 ** (n - 1)
        assert _wii2d_routes(n, table) is None

        with pytest.raises(ValueError, match="cost guard"):
            boolean.wii2d(table)

    def test_a_collapsing_chain_builds_past_the_dense_arity(self) -> None:
        r"""A structured table builds where a dense one of the same arity."""
        from esolangs.tools.boolean.wii2d import (
            _WII2D_MAX_INDEX_DOMAIN,
            _wii2d_chain,
            _wii2d_real_domain,
            _wii2d_symmetric_popcount_map,
        )

        n = (_WII2D_MAX_INDEX_DOMAIN).bit_length() + 1

        # depends on three of the n.
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
        r"""A chain that finds no merge is refused on width, naming that bound."""
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

        # Matched on the numbers, not.
        # the domain it measured and.
        # a substring match on "width.
        # The constant's *name* used to.
        # so in this pattern; a reader.
        # identifier leaking at them,.
        # 1025 is n == 7's worst case,.
        # need to merge, so an.
        with pytest.raises(
            ValueError, match=r"domain of 1025 points, past the 256-point width guard"
        ):
            boolean.wii2d(table)

    @pytest.mark.slow
    def test_decode_folds_past_the_guard(self) -> None:
        r"""A 64-point decode -- the ``n == 7`` domain -- folds correctly."""
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
        r"""Raising the guard yields a working ``n == 7`` program."""
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
        r"""The decode is a single pass: the head candidate, every step."""
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
        r"""Every eight-point pattern decodes under the single-candidate rule."""
        import itertools

        from esolangs.tools.boolean.wii2d import _wii2d_apply, _wii2d_decode

        for bits in itertools.product([0, 1], repeat=8):
            pattern = list(bits)
            ops = _wii2d_decode(pattern)
            assert ops is not None, pattern
            assert [_wii2d_apply(ops, x) for x in range(8)] == pattern

    def test_decode_constant_pattern_is_a_single_digit(self) -> None:
        r"""A constant column needs no folding at all, just a digit."""
        from esolangs.tools.boolean.wii2d import _wii2d_decode

        assert _wii2d_decode([0, 0, 0, 0]) == "0"
        assert _wii2d_decode([1, 1, 1, 1]) == "1"

    def test_decode_magnitude_abort_fires_on_a_constructed_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""The ratchet abort is reachable: a tiny bound refuses, the real."""
        import importlib

        from esolangs.tools.boolean.wii2d import _wii2d_decode

        module = importlib.import_module("esolangs.tools.boolean.wii2d")
        pattern = [0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0, 0, 0, 1, 0, 1]
        assert _wii2d_decode(list(pattern)) is not None
        monkeypatch.setattr(module, "_WII2D_MAX_MAGNITUDE", 1)
        assert _wii2d_decode(list(pattern)) is None

    @pytest.mark.slow  # ~2s: a real doubling-trap.
    def test_a_doubling_trap_pattern_is_refused_not_hung(self) -> None:
        r"""A domain-256 pattern that ratchets returns ``None`` in seconds."""
        import random

        from esolangs.tools.boolean.wii2d import _wii2d_decode

        rng = random.Random(9017)
        pattern = [rng.randint(0, 1) for _ in range(256)]
        assert _wii2d_decode(pattern) is None

    def test_decode_centre_cap_has_a_constructed_miss(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""A fixed fold-centre cap cannot make the greedy decoder total."""
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
        r"""The tail turns the last two values into their bits, either way."""
        from esolangs.tools.boolean.wii2d import _wii2d_apply, _wii2d_threshold

        rising = _wii2d_threshold({3: 0, 9: 1})
        assert _wii2d_apply(rising, 3) == 0
        assert _wii2d_apply(rising, 9) == 1
        falling = _wii2d_threshold({3: 1, 9: 0})
        assert _wii2d_apply(falling, 3) == 1
        assert _wii2d_apply(falling, 9) == 0
        assert _wii2d_threshold({7: 1}) == "1"

    def test_points_rejects_a_collision_needing_both_bits(self) -> None:
        r"""Two inputs on one value needing different bits is unrecoverable."""
        from esolangs.tools.boolean.wii2d import _wii2d_points

        assert _wii2d_points([0, 1, 2], [0, 1, 0]) == {0: 0, 1: 1, 2: 0}
        assert _wii2d_points([0, 1, 1], [0, 1, 0]) is None

    def test_compress_steers_with_an_increment(self) -> None:
        r"""When a plain halving would collide, ``+`` re-pairs the neighbours."""
        from esolangs.tools.boolean.wii2d import _wii2d_apply, _wii2d_compress

        values, ops = _wii2d_compress([2, 3], [0, 1], "")
        # the two inputs stay on.
        assert values[0] != values[1]
        # .
        assert [_wii2d_apply(ops, v) for v in (2, 3)] == values
        assert "+" in ops

    def test_compress_stops_when_halving_stops_moving(self) -> None:
        r"""Values a halving cannot separate end the compression."""
        from esolangs.tools.boolean.wii2d import _wii2d_compress

        values, ops = _wii2d_compress([-1, -1], [1, 1], "")
        assert values == [-1, -1]
        assert ops == "", "a stalled compression emits no ops"

    def test_a_fold_that_merges_nothing_is_not_offered(self) -> None:
        r"""A centre that leaves every point distinct buys no progress."""
        from esolangs.tools.boolean.wii2d import _wii2d_folds

        assert _wii2d_folds([0, 1], [0, 1]) == []
        # A state that already collides.
        # the plain nor the doubled.
        assert _wii2d_folds([2, 2], [0, 1]) == []

    def test_a_centre_too_far_out_to_spell_is_skipped(self) -> None:
        r"""A midpoint past the cap is correct but too wide for the grid."""
        from esolangs.tools.boolean.wii2d import _WII2D_MAX_CENTRE, _wii2d_folds

        near = _wii2d_folds([0, 4, 10], [1, 1, 0])
        assert near, "the positive control must fold"

        centre = (20000 + 20004) // 2
        assert centre > _WII2D_MAX_CENTRE
        assert _wii2d_folds([20000, 20004, 20010], [1, 1, 0]) == []

    def test_the_beam_search_gives_up_when_no_fold_survives(self) -> None:
        r"""With every fold rejected the search has nowhere to go."""
        import importlib

        # The package re-exports the.
        # name, so import the module.
        module = importlib.import_module("esolangs.tools.boolean.wii2d")
        from esolangs.tools.boolean.wii2d import _wii2d_decode

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_wii2d_folds", lambda *_: [])
            assert _wii2d_decode([0, 1, 1, 0]) is None

    def test_folds_that_never_shrink_run_the_loop_out(self) -> None:
        r"""A fold that returns its own state exhausts the iteration bound."""
        import importlib

        # The package re-exports the.
        # name, so import the module.
        module = importlib.import_module("esolangs.tools.boolean.wii2d")
        from esolangs.tools.boolean.wii2d import _wii2d_decode

        def stuck(
            values: list[int], _bits: list[int]
        ) -> list[tuple[int, int, int, str, list[int]]]:
            return [(max(values), len(set(values)), 1, "+", list(values))]

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_wii2d_folds", stuck)
            # four distinct live values, so.
            assert _wii2d_decode([0, 1, 1, 0, 1, 0, 0, 1]) is None

        # A fold that collides two.
        # state with no live map at.
        def collides(
            _values: list[int], _bits: list[int]
        ) -> list[tuple[int, int, int, str, list[int]]]:
            return [(2, 1, 1, "", [2, 2, 2, 2])]

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_wii2d_folds", collides)
            assert _wii2d_decode([0, 1, 1, 0]) is None

    def test_chain_is_a_junction_chain_then_a_decode(self) -> None:
        r"""The constructed routes have the shape the docstring claims."""
        from esolangs.tools.boolean.wii2d import (
            _WII2D_JUNCTIONS,
            _wii2d_apply,
            _wii2d_routes,
        )

        n = 4
        # not parity and not symmetric,.
        table = "0001011001101011"
        result = _wii2d_routes(n, table)
        assert result is not None
        start, routes = result
        assert start == 0
        assert len(routes) == n
        # every junction but the last.
        for pair in routes[:-1]:
            assert pair in _WII2D_JUNCTIONS
        # and the chain plus decode.
        for combo in range(2**n):
            bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
            value = start
            for i, bit in enumerate(bits):
                value = _wii2d_apply(routes[i][bit], value)
            assert value == int(table[combo]), f"inputs {bits}"

    def test_horner_is_the_catalogue_fallback(self) -> None:
        r"""Horner ends the catalogue, and is legal at every level."""
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
        # Horner merges nothing, so the.
        assert sorted(value for _, value in states) == list(range(2 ** (n - 1)))

    def test_symmetric_tables_use_a_popcount_chain(self) -> None:
        r"""A symmetric table decodes over ``n`` points, not ``2 ** (n - 1)``."""
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
        r"""An exactly-k-of-n table is symmetric but not monotone, and fits."""
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
        r"""Constructed routes evaluate to the table for all 256 three-bit."""
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

    def test_a_dense_seven_input_table_builds_and_runs(self) -> None:
        r"""A dense ``n == 7`` table builds, and every one of its 128 fills."""
        table = (
            "0011001100111000100001011111101000101111111010101001100110101001"
            "1100011100100000111001110111101101111101101001111110001111101011"
        )
        assert len(table) == 128  # n == 7.

        from esolangs.tools.boolean.wii2d import _wii2d_symmetric_popcount_map

        # not symmetric, so this is the.
        # chain that lets symmetric.
        assert _wii2d_symmetric_popcount_map(7, table) is None

        template = boolean.wii2d(table)
        for combo in range(128):
            bits = [(combo >> (6 - i)) & 1 for i in range(7)]
            assert self.run_chain(template, bits) == table[combo], f"inputs {bits}"

    def test_a_branch_that_will_not_decode_refuses_the_chain(self) -> None:
        r"""Both halves of the index chain have to decode, or there is no route."""
        module = importlib.import_module("esolangs.tools.boolean.wii2d")
        from esolangs.tools.boolean.wii2d import _wii2d_routes

        # n == 2 has a closed form and.
        # chain, neither of which.
        # takes a non-symmetric table.
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(module, "_wii2d_decode", lambda *_a, **_k: None)
            assert _wii2d_routes(3, "00010111") is None

    def test_wii2d_raises_when_the_construction_finds_no_route(self) -> None:
        r"""``wii2d`` surfaces a construction failure as a ``ValueError``."""
        from esolangs.tools.boolean import parameterized

        wii2d_mod = importlib.import_module("esolangs.tools.boolean.wii2d")

        with (
            patch.object(wii2d_mod, "_wii2d_routes", return_value=None),
            pytest.raises(ValueError, match="no route"),
        ):
            parameterized.wii2d("0110")

    def test_layout_embeds_a_nonzero_start_digit(self) -> None:
        r"""A nonzero ``start`` writes an initial digit before the chain runs."""
        from esolangs.tools.boolean.wii2d import _wii2d_layout

        template = "\n".join(_wii2d_layout(1, 5, [("", "+")]))
        for bit, expected in ((0, "5"), (1, "6")):
            assert self.run_chain(template, [bit]) == expected
        # The digit's own column is.
        # template cannot see it: a.
        # computes the same answer.
        assert template == (">5{X0} >" + "+" * 48 + "~.\n! >+^")

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("0110", 76),
            ("00000001", 105),
            ("00000010", 105),
            ("00000110", 124),
        ],
    )
    def test_the_template_has_an_exact_length(self, table: str, length: int) -> None:
        r"""The emitted template's size, per table."""
        assert len(boolean.wii2d(table)) == length

    def test_the_xor_template_is_exact(self) -> None:
        r"""XOR's template, spelled out."""
        assert boolean.wii2d("0110") == (
            ">{X0}->{X1}+>" + "+" * 48 + "~.\n!>*^\n    >s^"
        )

    @pytest.mark.parametrize(
        ("table", "routes"),
        [
            ("01101001", (0, [("", "+"), ("", "-s"), ("", "-s")])),
            ("00000000", (0, [("", "+"), ("", "+"), ("0", "0")])),
        ],
    )
    def test_the_route_plan_is_exact(
        self, table: str, routes: tuple[int, list[tuple[str, str]]]
    ) -> None:
        r"""The per-level route pairs the chain search settles on."""
        from esolangs.tools.boolean.wii2d import _wii2d_routes

        n = len(table).bit_length() - 1
        assert _wii2d_routes(n, table) == routes

    def test_decode_and_threshold_spellings_are_exact(self) -> None:
        r"""Two helpers whose output is a spelling, not a value."""
        from esolangs.tools.boolean.wii2d import _wii2d_decode, _wii2d_threshold

        assert _wii2d_decode([0, 0, 0, 0, 1, 1, 0, 1]) == "*-s+/+/+//+//-s+/-s-//+"
        assert _wii2d_threshold({3: 0, 9: 1}) == "---------////+"


class TestCircuitDiagram:
    r"""The Circuit Diagram generator (a real gate network, input-reading)."""

    @staticmethod
    def run_table(table: str) -> str:
        r"""Return the generated program's output for every input, in order."""
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
        r"""All sixteen two-input functions, each over all four inputs."""
        assert self.run_table(table) == table

    @pytest.mark.parametrize("table", ["01", "10", "00", "11"])
    def test_every_one_input_table(self, table: str) -> None:
        assert self.run_table(table) == table

    @pytest.mark.parametrize(
        "table",
        ["00010111", "01101001", "11110000", "00000000", "11111111"],
    )
    def test_three_input_tables(self, table: str) -> None:
        r"""Majority, parity, a projection, and both constants."""
        assert self.run_table(table) == table

    @pytest.mark.parametrize(
        ("table", "tildes"),
        [
            ("0001", 0),  # AND: every minterm bit is 1,.
            ("01", 0),  # identity: likewise.
            ("10", 1),  # NOT: its one minterm selects.
            ("0110", 2),  # XOR: both inputs appear.
        ],
    )
    def test_only_needed_complements_are_built(self, table: str, tildes: int) -> None:
        r"""A ``~`` is drawn only when some minterm selects that complement."""
        from esolangs.tools.boolean.circuit_diagram import circuit_diagram

        assert circuit_diagram(table).count("~") == tildes

    def test_a_dense_table_is_drawn_as_its_complement(self) -> None:
        r"""More ones than zeros costs less built from the zero rows."""
        from esolangs.tools.boolean.circuit_diagram import circuit_diagram

        dense = circuit_diagram("11111110")  # NAND3: seven ones.
        sparse = circuit_diagram("00000001")  # its complement: one.
        assert len(dense) < 2 * len(sparse)
        # both compute their own table,.
        assert self.run_table("11111110") == "11111110"
        assert self.run_table("00000001") == "00000001"

    def test_a_constant_table_is_never_complemented(self) -> None:
        r"""It is already one gate, so complementing only swaps the glyph."""
        assert self.run_table("1111") == "1111"
        assert self.run_table("0000") == "0000"

    def test_four_input_primality(self) -> None:
        r"""The same function the wiki's own worked example computes."""
        primes = {n for n in range(2, 16) if all(n % d for d in range(2, n))}
        table = "".join("1" if n in primes else "0" for n in range(16))
        assert self.run_table(table) == table

    def test_each_run_prints_exactly_one_bit(self) -> None:
        r"""The output wire is live for exactly one generation."""
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
        r"""Each bit arrives on its own line, which the spec makes an input."""
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


# 6.2s over 99 tests: builds.
@pytest.mark.medium
class TestCircuitDiagramLayoutGuards:
    r"""The layout's collision checks, reached by constructing the state."""

    @staticmethod
    def _layout() -> object:
        from esolangs.tools.boolean.circuit_diagram import _Layout

        return _Layout()

    def test_two_signals_may_not_run_the_same_way_through_a_cell(self) -> None:
        layout = self._layout()
        layout.run_horizontal(2, 5, 4, 7)
        with pytest.raises(AssertionError) as caught:
            layout.run_horizontal(2, 5, 4, 9)
        assert str(caught.value) == "two signals run horizontal through (3, 4)"
        layout = self._layout()
        layout.run_vertical(3, 2, 6, 1)
        with pytest.raises(AssertionError) as caught:
            layout.run_vertical(3, 2, 6, 2)
        assert str(caught.value) == "two signals run vertical through (3, 3)"

    def test_partly_overlapping_runs_clash_at_the_first_shared_cell(self) -> None:
        r"""Runs are intervals now, so overlap is not only exact re-tracing."""
        layout = self._layout()
        layout.run_horizontal(2, 6, 4, 7)
        with pytest.raises(AssertionError) as caught:
            layout.run_horizontal(4, 8, 4, 9)
        assert str(caught.value) == "two signals run horizontal through (5, 4)"

    def test_one_signal_may_reclaim_its_own_cells(self) -> None:
        r"""A repeated claim by the same signal is the ordinary case."""
        layout = self._layout()
        layout.run_horizontal(2, 5, 4, 7)
        layout.run_horizontal(2, 5, 4, 7)
        assert layout.render().split("\n")[4] == "   --"

    def test_two_signals_may_cross_at_right_angles(self) -> None:
        r"""The clash is per direction: crossing wires share the cell as ``=``."""
        layout = self._layout()
        layout.run_horizontal(2, 5, 4, 1)
        layout.run_vertical(3, 2, 6, 2)
        rows = layout.render().split("\n")
        assert rows[3] == "   |"
        assert rows[4] == "   =-"
        assert rows[5] == "   |"

    @pytest.mark.parametrize(
        ("run", "args"),
        [("run_horizontal", (2, 5, 4, 1)), ("run_vertical", (3, 2, 6, 1))],
    )
    def test_a_wire_may_not_cross_a_glyph(
        self, run: str, args: tuple[int, ...]
    ) -> None:
        r"""Both run directions consult the glyphs along their line."""
        layout = self._layout()
        layout.glyph(3, 4, "&")
        with pytest.raises(AssertionError) as caught:
            getattr(layout, run)(*args)
        assert str(caught.value) == "wire crosses glyph at (3, 4)"

    def test_a_glyph_may_not_land_on_a_glyph(self) -> None:
        layout = self._layout()
        layout.glyphs[(1, 1)] = "&"
        with pytest.raises(AssertionError) as caught:
            layout._check_free(1, 1)  # noqa: SLF001
        assert str(caught.value) == "two glyphs at (1, 1)"

    @pytest.mark.parametrize("axis", ["horizontal", "vertical"])
    def test_a_glyph_may_not_land_on_a_wire(self, axis: str) -> None:
        r"""Both wire tables are consulted, not just the first."""
        layout = self._layout()
        if axis == "horizontal":
            layout.run_horizontal(0, 2, 1, 1)
        else:
            layout.run_vertical(1, 0, 2, 1)
        with pytest.raises(AssertionError) as caught:
            layout._check_free(1, 1)  # noqa: SLF001
        assert str(caught.value) == "glyph at (1, 1) lands on a wire"

    def test_a_free_cell_takes_a_glyph(self) -> None:
        self._layout()._check_free(1, 1)  # noqa: SLF001

    def test_a_run_between_touching_junctions_records_nothing(self) -> None:
        r"""The span is exclusive, so neighbours leave no cell to claim."""
        layout = self._layout()
        layout.run_vertical(3, 4, 4, 1)
        layout.run_vertical(3, 4, 5, 1)
        assert layout.render() == ""
        # A real span through the same.
        # above rejected the empty.
        layout.run_vertical(3, 2, 6, 1)
        assert layout.render() != ""

    def test_the_clash_scan_keeps_looking_after_its_first_hit(self) -> None:
        r"""The reported cell is the earliest, not the first one found."""
        from esolangs.tools.boolean.circuit_diagram import _Layout

        late_is_earlier = _Layout._clash(  # noqa: SLF001
            [(6, 9, 1), (2, 4, 2)], None, 0, 10, 9
        )
        assert late_is_earlier == (2, True)
        early_stays = _Layout._clash([(2, 4, 1), (6, 9, 2)], None, 0, 10, 9)  # noqa: SLF001
        assert early_stays == (2, True)

    @pytest.mark.parametrize(
        ("dx", "dy"),
        [(dx, dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (dx, dy) != (0, 0)],
    )
    def test_adjacent_junctions_of_different_signals_are_rejected(
        self, dx: int, dy: int
    ) -> None:
        r"""All eight neighbours, diagonals included, merge and so are refused."""
        layout = self._layout()
        layout.junctions[(5, 5)] = 1
        layout.junctions[(5 + dx, 5 + dy)] = 2
        with pytest.raises(AssertionError) as caught:
            layout._check_junction_spacing()  # noqa: SLF001
        assert str(caught.value) in (
            f"junctions of different signals touch at (5, 5) and ({5 + dx}, {5 + dy})",
            f"junctions of different signals touch at ({5 + dx}, {5 + dy}) and (5, 5)",
        )

    def test_junctions_of_the_same_signal_may_touch(self) -> None:
        r"""One signal's own junctions are a single wiring already."""
        layout = self._layout()
        layout.junctions[(5, 5)] = 1
        layout.junctions[(6, 6)] = 1
        layout._check_junction_spacing()  # noqa: SLF001

    def test_junctions_one_clear_of_each_other_are_accepted(self) -> None:
        r"""Distance 2 is what every real layout keeps, and it is legal."""
        layout = self._layout()
        layout.junctions[(5, 5)] = 1
        layout.junctions[(7, 5)] = 2
        layout._check_junction_spacing()  # noqa: SLF001

    @pytest.mark.parametrize(
        ("table", "rows", "columns"),
        [
            ("01", 1, 4),
            ("0001", 7, 11),
            ("0110", 23, 35),
            # 91 columns before gate groups.
            # what moves when they stop.
            # reuse gives back columns and.
            ("00010111", 61, 61),
            # Four inputs, where the two.
            # left fold with no reuse, 99.
            # once the folds were balanced.
            # change gives back a band.
            ("0110100110010110", 147, 87),
        ],
    )
    def test_the_drawing_has_exact_dimensions(
        self, table: str, rows: int, columns: int
    ) -> None:
        r"""The band and column steps place every part of the drawing."""
        from esolangs.tools.boolean.circuit_diagram import circuit_diagram

        drawing = circuit_diagram(table).split("\n")
        assert len(drawing) == rows
        assert max(len(row) for row in drawing) == columns

    def test_balancing_the_folds_keeps_the_width_logarithmic(self) -> None:
        r"""Each extra input doubles the minterms and costs a bounded step."""
        widths = {}
        for n in (3, 4, 5, 6):
            table = "".join(str(bin(i).count("1") % 2) for i in range(2**n))
            drawing = boolean.circuit_diagram(table)
            widths[n] = max(len(row) for row in drawing.splitlines())
        assert widths == {3: 61, 4: 87, 5: 113, 6: 133}
        steps = [widths[n + 1] - widths[n] for n in (3, 4, 5)]
        assert max(steps) <= 30, steps

    def test_a_balanced_fold_holds_only_its_depth_live(self) -> None:
        r"""The halves are drawn one after the other, not all up front."""
        # Sixteen minterms at n=5:.
        # buses, which at two columns.
        table = "".join(str(bin(i).count("1") % 2) for i in range(32))
        drawing = boolean.circuit_diagram(table)
        assert max(len(row) for row in drawing.splitlines()) == 113

    def test_real_layouts_never_come_within_one_cell(self) -> None:
        r"""The generator's spacing keeps every table clear of the guard."""
        from esolangs.tools.boolean.circuit_diagram import _Layout, circuit_diagram

        closest = []
        original = _Layout._check_junction_spacing  # noqa: SLF001

        def record(layout: object) -> None:
            items = list(layout.junctions.items())
            for index, ((x1, y1), first) in enumerate(items):
                for (x2, y2), second in items[index + 1 :]:
                    if first != second:
                        closest.append(max(abs(x1 - x2), abs(y1 - y2)))
            original(layout)

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(_Layout, "_check_junction_spacing", record)
            for table_int in range(16):
                circuit_diagram(format(table_int, "04b"))
        assert closest, "no layout carried two signals' junctions"
        assert min(closest) >= 2

    @staticmethod
    def _run_at(table: str, width: int | None) -> str:
        r"""The banded program's output for every input, in table order."""
        from esolangs.interpreters.grid_based.circuit_diagram import run
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.boolean.circuit_diagram import circuit_diagram

        n = len(table).bit_length() - 1
        program = circuit_diagram(table, width).split("\n")
        results = []
        for index in range(len(table)):
            stdin = "".join(f"{bit}\n" for bit in format(index, f"0{n}b"))
            io = ScriptedIO(stdin)
            run(program, io)
            results.append(io.getvalue())
        return "".join(results)

    def test_a_width_bands_the_drawing_and_it_still_computes(self) -> None:
        r"""Banding carries the live signals left; the circuit is unchanged."""
        from esolangs.tools.boolean.circuit_diagram import circuit_diagram

        # ``00101111`` at 30 is the.
        # dense table is drawn from its.
        # gate sits past the whole.
        # width because only ``gate``.
        for table in ("01101001", "0110100110010110", "00010111", "00101111"):
            flat = circuit_diagram(table)
            wide = max(len(row) for row in flat.splitlines())
            floor = max(len(row) for row in circuit_diagram(table, 1).splitlines())
            for width in (1, 30, 50, 60, 80, wide):
                narrow = circuit_diagram(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                assert self._run_at(table, width) == table, (table, width)

    def test_banding_brings_every_arity_inside_eighty(self) -> None:
        r"""Which is the point: unbanded, parity clears 80 columns at n == 4."""
        from esolangs.tools.boolean.circuit_diagram import circuit_diagram

        for n in (4, 5, 6):
            table = "".join(str(bin(i).count("1") % 2) for i in range(2**n))
            flat = circuit_diagram(table)
            banded = circuit_diagram(table, 80)
            assert max(len(row) for row in flat.splitlines()) > 80, n
            assert max(len(row) for row in banded.splitlines()) <= 80, n
            # and it costs rows, which is.
            assert len(banded.splitlines()) > len(flat.splitlines()), n

    def test_a_band_must_re_carry_what_an_earlier_one_moved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""Forgetting a carried signal hands its column away while it is live."""
        import importlib

        from esolangs.tools.boolean.circuit_diagram import _Builder

        module = importlib.import_module("esolangs.tools.boolean.circuit_diagram")
        original = getattr(_Builder, "_band")  # noqa: B009 - SLF001 otherwise

        def forgetful(self: _Builder) -> None:
            original(self)
            self.live.clear()

        table = "".join(str(bin(i).count("1") % 2) for i in range(32))
        monkeypatch.setattr(_Builder, "_band", forgetful)
        with pytest.raises(AssertionError, match="two signals run vertical"):
            module.circuit_diagram(table, 40)
        monkeypatch.undo()
        # and with the carry kept, the.
        assert self._run_at(table, 40) == table


class TestSuperSNUSP:
    r"""The Super SNUSP generator (an ANF evaluator over a value stack)."""

    def test_cost_model_selects_the_emitted_anf(self) -> None:
        r"""The selector prices both ANF layouts exactly through three inputs."""
        from esolangs.tools.boolean.helpers import essential_inputs, read_at
        from esolangs.tools.boolean.super_snusp import (
            _TWO_INPUT_SHORT,
            _anf_cost,
            _emit_anf,
            super_snusp,
        )

        for n in range(1, 4):
            for value in range(1 << (1 << n)):
                table = format(value, f"0{1 << n}b")
                used = essential_inputs(table, n)
                reduced = read_at(table, used, n)
                full = list(range(n))
                full_cost = _anf_cost(n, table, full)
                reduced_cost = _anf_cost(n, reduced, used)
                assert full_cost == len(_emit_anf(n, table, full))
                assert reduced_cost == len(_emit_anf(n, reduced, used))
                if table not in _TWO_INPUT_SHORT:
                    assert len(super_snusp(table)) == min(full_cost, reduced_cost)

    @staticmethod
    def run_table(table: str) -> str:
        r"""Return the generated program's output for every input, in order."""
        from esolangs.interpreters.grid_based.super_snusp import run
        from esolangs.interpreters.io import ScriptedIO
        from esolangs.tools.boolean.super_snusp import super_snusp

        n = len(table).bit_length() - 1
        program = super_snusp(table).splitlines()
        results = []
        for index in range(len(table)):
            bits = format(index, f"0{n}b")
            stdin = "".join(f"{bit}\n" for bit in bits)
            scripted = ScriptedIO(stdin)
            run(program, scripted)
            results.append(scripted.getvalue().strip())
        return "".join(results)

    @pytest.mark.parametrize("table", [format(i, "04b") for i in range(16)])
    def test_every_two_input_table(self, table: str) -> None:
        r"""All sixteen two-input functions, each over all four inputs."""
        assert self.run_table(table) == table

    @pytest.mark.parametrize("table", ["01", "10", "00", "11"])
    def test_every_one_input_table(self, table: str) -> None:
        assert self.run_table(table) == table

    @pytest.mark.parametrize(
        "table",
        [
            "01101001",  # parity: every ANF coefficient.
            "00010111",  # majority.
            "11101000",  # its complement, so the.
            "10000000",  # AND3: one minterm, the.
            "00000000",
            "11111111",
        ],
    )
    def test_three_input_tables(self, table: str) -> None:
        r"""Parity, majority, AND3 and both constants at three inputs."""
        assert self.run_table(table) == table

    @pytest.mark.parametrize(
        "table",
        ["11110000", "00001111", "11001100", "00110011", "10101010", "01010101"],
    )
    def test_a_table_ignoring_inputs_still_computes_it(self, table: str) -> None:
        r"""Dependency reduction keeps the answer over the full input space."""
        assert self.run_table(table) == table

    def test_a_four_input_table_builds_and_runs(self) -> None:
        r"""The construction is not two- and three-input special cases."""
        assert self.run_table("0110100110010110") == "0110100110010110"

    @pytest.mark.parametrize(
        "table", ["01", "0110", "0001", "01101001", "11110000", "00010111"]
    )
    def test_every_input_is_consumed(self, table: str) -> None:
        r"""One ``,`` per input, including inputs the answer ignores."""
        from esolangs.tools.boolean.super_snusp import super_snusp

        n = len(table).bit_length() - 1
        assert super_snusp(table).count(",") == n

    @pytest.mark.parametrize("table", ["01", "0000", "0110", "01101001", "11110000"])
    def test_every_program_starts_with_the_marker(self, table: str) -> None:
        r"""``"`` pins the entry point rather than inheriting the default."""
        from esolangs.tools.boolean.super_snusp import super_snusp

        assert super_snusp(table).startswith('"')

    def test_the_short_forms_are_what_the_generator_emits(self) -> None:
        r"""The five hand-written two-input forms are used verbatim."""
        from esolangs.tools.boolean.super_snusp import _TWO_INPUT_SHORT, super_snusp

        for table, form in _TWO_INPUT_SHORT.items():
            assert super_snusp(table) == '"' + form

    def test_the_general_build_is_used_off_the_short_table(self) -> None:
        r"""A two-input table with no short form is built by the evaluator."""
        from esolangs.tools.boolean.super_snusp import _TWO_INPUT_SHORT, super_snusp

        assert "0001" not in _TWO_INPUT_SHORT
        assert super_snusp("0001") == '"48{,->,->>1<<<{>>>&<<{>>&{<^>48{<+.'

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("1010", 28),  # one dependency at two inputs.
            ("1111", 17),  # constant: the reduction drops.
            ("00000000", 18),  # constant at three.
            ("00000011", 39),  # depends on the last two of.
        ],
    )
    def test_the_reduced_build_is_the_one_emitted(
        self, table: str, length: int
    ) -> None:
        r"""A table that ignores an input is emitted over its essential ones."""
        from esolangs.tools.boolean.super_snusp import super_snusp

        assert len(super_snusp(table)) == length

    def test_a_malformed_table_is_rejected(self) -> None:
        from esolangs.tools.boolean.super_snusp import super_snusp

        with pytest.raises(ValueError, match="power-of-two"):
            super_snusp("010")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            super_snusp("012x")


class TestAlightWidth:
    r"""Alight's boustrophedon, which is the only way its line can fold."""

    @staticmethod
    def _run(program: str, bits: list[str]) -> str:
        import esolangs

        stdin = "".join(f"{bit}\n" for bit in bits)
        return esolangs.run("Alight", program, stdin=stdin, timeout=5.0).strip()

    def test_a_width_folds_the_walk_and_it_still_computes(self) -> None:
        r"""The folded walk computes what the straight one did."""
        for table in ("0110", "01101001", "0110100110010110"):
            n = len(table).bit_length() - 1
            flat = boolean.alight(table)
            wide = max(len(row) for row in flat.splitlines())
            floor = max(len(row) for row in boolean.alight(table, 1).splitlines())
            assert floor < wide, f"{table} never narrows"
            for width in (1, 40, 60, wide):
                narrow = boolean.alight(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                for combo in range(2**n):
                    bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                    assert self._run(narrow, bits) == table[combo], (table, width)

    def test_splitting_the_literal_takes_the_floor_off_the_table(self) -> None:
        r"""The literal was the floor; chunking it means the arity no longer is."""
        floors = {}
        for n in (4, 5, 6, 7):
            table = "".join(str(bin(i).count("1") % 2) for i in range(2**n))
            narrow = boolean.alight(table, 1)
            floors[n] = max(len(row) for row in narrow.splitlines())
            # the unsplit literal alone.
            literal = len(f'set r at{{"{table}", i+0.5}};')
            assert floors[n] < literal or n == 4, (n, floors[n], literal)
        assert max(floors.values()) - min(floors.values()) <= 4, floors

    def test_a_width_is_met_at_every_arity(self) -> None:
        r"""Which is what splitting the literal buys: 80 columns holds at n=7."""
        for n in (4, 5, 6, 7):
            table = "".join(str(bin(i).count("1") % 2) for i in range(2**n))
            for width in (60, 80):
                narrow = boolean.alight(table, width)
                assert max(len(row) for row in narrow.splitlines()) <= width, (n, width)

    def test_a_chunk_and_its_guard_stay_on_one_row(self) -> None:
        r"""``skip`` guards the *next command along the heading*."""
        table = "".join(str(bin(i).count("1") % 2) for i in range(64))
        rows = boolean.alight(table, 60).splitlines()
        seen = 0
        for row in rows:
            for text in (row, row[::-1]):
                for index in range(len(text) - 4):
                    if text[index : index + 4] == "skip":
                        seen += 1
                        assert "set r at{" in text[index:], text
        assert seen, "no guarded chunk in the drawing"

    def test_a_folded_row_keeps_the_space_inside_its_turn(self) -> None:
        r"""``turn right`` has a space, and a vertical turn writes it as a cell."""
        narrow = boolean.alight("0110100110010110", 40)
        rows = narrow.splitlines()
        assert any(row.strip() == "" and row != "" for row in rows), (
            "the turn's own space was stripped away"
        )
        assert "turnright" not in narrow.replace("\n", "")


class TestSuperSNUSPWidth:
    r"""SNUSP's mirrors, which make this the cheapest fold of any generator."""

    @staticmethod
    def _run(program: str, bits: list[str]) -> str:
        import esolangs

        stdin = "".join(f"{bit}\n" for bit in bits)
        return esolangs.run("Super SNUSP", program, stdin=stdin, timeout=5.0).strip()

    def test_a_width_folds_the_line_and_it_still_computes(self) -> None:
        r"""The folded pointer computes what the straight one did."""
        for table in ("0110", "01101001", "0110100110010110"):
            n = len(table).bit_length() - 1
            flat = boolean.super_snusp(table)
            wide = max(len(row) for row in flat.splitlines())
            floor = max(len(row) for row in boolean.super_snusp(table, 1).splitlines())
            assert floor < wide, f"{table} never narrows"
            for width in (1, 6, 12, 20, wide):
                narrow = boolean.super_snusp(table, width)
                columns = max(len(row) for row in narrow.splitlines())
                assert columns <= max(width, floor), (table, width, columns)
                for combo in range(2**n):
                    bits = [str((combo >> (n - 1 - i)) & 1) for i in range(n)]
                    assert self._run(narrow, bits) == table[combo], (table, width)

    def test_both_mirrors_are_used(self) -> None:
        r"""A program long enough to fold twice turns round and back again."""
        table = "".join(str(bin(i).count("1") % 2) for i in range(32))
        narrow = boolean.super_snusp(table, 12)
        assert "\\" in narrow, narrow
        assert "/" in narrow, narrow
        assert narrow.count("\\") >= 2, "an east-to-west turn is two mirrors"
        assert narrow.count("/") >= 2, "so is a west-to-east one"

    def test_a_digit_run_is_never_split_by_a_fold(self) -> None:
        r"""``48`` has to stay on one row: a mirror in between would make it 4,."""
        for width in range(4, 20):
            narrow = boolean.super_snusp("0110100110010110", width)
            assert "48" in narrow, (width, narrow)
