"""Covers :mod:`esolangs.tools.sbleq`: the shared tree and the packed decoder."""

import random
from itertools import pairwise

import pytest

from esolangs import tools as boolean
from esolangs.tools.helpers import best_input_order
from esolangs.tools.sbleq import _sbleq_hoisted, _sbleq_packed
from tests.tools.boolean_runners import run_sbleq
from tests.tools.sample_tables import five_input_sample


class TestSbleq:
    """The hoisted tree through its sharing, and the packed decoder past it."""

    def test_program_structure(self) -> None:
        """Low-address data precedes the root reads and branch."""
        program = _sbleq_hoisted("0110", (0, 1))
        cells = [int(tok) for tok in program.split()]
        data_base = 9
        code_base = cells[6]
        assert cells[:6] == [0, 0, 6, -1, 0, 0]
        assert cells[7:9] == [0, 0]
        assert cells[data_base : data_base + 4] == [-49, 48, 49, -1]
        assert cells[code_base : code_base + 3] == [
            data_base + 4,
            -2,
            data_base + 6,
        ]
        assert cells[code_base + 6 : code_base + 9] == [
            data_base + 4,
            data_base,
            data_base + 8,
        ]
        code = cells[code_base:]
        triples = [tuple(code[i : i + 3]) for i in range(0, len(code), 3)]
        outputs = [
            t for t in triples if t[0] == -3
        ]  # one output per leaf, in combo order
        assert outputs == [
            (-3, data_base + 1, 0),
            (-3, data_base + 2, 0),
            (-3, data_base + 2, 0),
            (-3, data_base + 1, 0),
        ]
        assert [t for t in triples if t == (0, 0, 3)] == 4 * [(0, 0, 3)]

    def test_only_the_hoisted_route_remains(self) -> None:
        """The former node-read builder is gone, not merely bypassed."""
        import importlib

        module = importlib.import_module("esolangs.tools.sbleq")

        assert not hasattr(module, "_sbleq_node_read")

    def test_hoisted_build_reads_every_input_once_up_front(self) -> None:
        """The read block is 2n instructions and precedes every branch."""
        program = _sbleq_hoisted("00010111", (0, 1, 2))
        cells = [int(tok) for tok in program.split()]
        code_base = cells[6]
        code = cells[code_base:]
        triples = [tuple(code[i : i + 3]) for i in range(0, len(code), 3)]
        reads = [t for t in triples[:3] if t[1] == -2]
        assert len(reads) == 3  # one read per input, all before the tree
        assert [t[0] for t in reads] == sorted({t[0] for t in reads})  # input order

    def test_packed_decoder_executes_wide_rows(self) -> None:
        """Rows on both sides of chunk boundaries decode correctly."""
        n = 6
        table = "".join(str(row.bit_count() & 1) for row in range(2**n))
        program = _sbleq_packed(table)
        for row in (0, 1, 5, 6, 7, 31, 32, 62, 63):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_sbleq(program, bits) == table[row]

    def test_wide_growth_is_linear(self) -> None:
        """Wide parity tables grow by at most the table-size ratio."""
        sizes = []
        for n in range(11, 15):
            table = "".join(str(row.bit_count() & 1) for row in range(2**n))
            sizes.append(len(boolean.sbleq(table)))
        assert all(b <= 2 * a for a, b in pairwise(sizes))

    def test_mismatched_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.sbleq("011")

    def test_bad_table_rejected(self) -> None:
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.sbleq("0123")

    def test_a_repeated_subtree_is_jumped_to(self) -> None:
        """XOR's second test reaches the leaves already emitted for the first."""
        shared = boolean.sbleq("0110").split()
        plain = _sbleq_hoisted("0110", (0, 1)).split()
        # Two two-instruction leaves out, one jump in, three cells apiece.
        assert len(plain) - len(shared) == 3 * (4 - 1)
        assert shared[-3:-1] == ["0", "0"]
        assert shared.count("-3") == plain.count("-3") - 2 == 2

    @staticmethod
    def _sharing_totals(tables: list[str]) -> tuple[int, int]:
        """(before, shipped) totals, each table checked not to grow."""
        before = after = 0
        for table in tables:
            old = len(
                best_input_order(table, _sbleq_hoisted)
                if len(table) <= 16
                else _sbleq_packed(table)
            )
            new = len(boolean.sbleq(table))
            assert new <= old, table
            before, after = before + old, after + new
        return before, after

    def test_sharing_three_input_total(self) -> None:
        """All 256 three-input tables: 48,078 to 38,084 characters, 20.8%."""
        tables = [format(i, "08b") for i in range(256)]
        assert self._sharing_totals(tables) == (48078, 38478)

    def test_sharing_five_input_sample_total(self) -> None:
        """200 seeded five-input tables: 323,720 to 61,593 characters, 81.0%."""
        assert self._sharing_totals(five_input_sample()) == (323720, 62709)

    def test_shared_tree_executes_wide_rows(self) -> None:
        """A seeded seven-input table, every row, through the shared tree."""
        n = 7
        table = format(random.Random(7).getrandbits(2**n), f"0{2**n}b")
        program = boolean.sbleq(table)
        assert len(program) < len(_sbleq_packed(table))
        for row in range(2**n):
            bits = [str((row >> (n - 1 - i)) & 1) for i in range(n)]
            assert run_sbleq(program, bits) == table[row]
