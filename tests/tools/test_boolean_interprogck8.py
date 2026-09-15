"""Unit tests for the Interprogck8 boolean generator.

Every claim here is made by running the emitted program: the corridor is
routed by ``DownAccLines``, whose off-by-one is the whole construction,
so reading the source proves nothing about where a chain dismounts.
"""

import hashlib

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.interprogck8 import _Machine
from esolangs.tools import interprogck8
from esolangs.tools.interprogck8 import _assemble, _validate
from esolangs.vm import run_until_halt_or_cycle
from tests.tools.boolean_runners import run_interprogck8


def _dense_table(n: int) -> str:
    """The contract suite's dense pseudo-random table, the worst to fold."""
    digest = hashlib.sha256(f"dense:{n}".encode()).digest()
    bits: list[str] = []
    block = 0
    while len(bits) < 2**n:
        digest = hashlib.sha256(digest + bytes([block & 255])).digest()
        bits.extend(str(byte & 1) for byte in digest)
        block += 1
    return "".join(bits[: 2**n])


def _tables(n: int) -> list[str]:
    return [bin(v)[2:].zfill(2**n) for v in range(2 ** (2**n))]


class TestExhaustive:
    @pytest.mark.parametrize("n", [1, 2, pytest.param(3, marks=pytest.mark.slow)])
    def test_every_table_of_every_arity(self, n: int) -> None:
        """All 4, 16 and 256 tables, every row, executed.

        This is the phase-1 gate answered by construction rather than by
        argument: a full decision tree routes through ``DownAccLines``
        alone, and the current-function slot is never touched.
        """
        for table in _tables(n):
            program = interprogck8(table)
            assert "<" not in program, "routing must not use the function slot"
            for row in range(2**n):
                bits = list(bin(row)[2:].zfill(n))
                assert run_interprogck8(program, bits) == table[row], (
                    f"{table} row {row}"
                )


class TestReads:
    @pytest.mark.parametrize("table", ["00000000", "11111111", "01101001"])
    def test_a_folded_table_still_consumes_its_inputs(self, table: str) -> None:
        """Every path reads all three digits before printing.

        The reads are the interface: leaving a bit unread desynchronises
        whatever runs on the same stream next.
        """
        program = interprogck8(table)
        io = ScriptedIO("0\n1\n1\n")
        machine = _Machine(program.splitlines(), io)
        run_until_halt_or_cycle(machine)
        assert io.position() == 3, "a constant table must still read all three"
        assert io.getvalue() == table[0b011]


class TestCorridor:
    """Past n=3 flights cross whole subtrees on the shared corridor."""

    @pytest.mark.parametrize("n", [4, 5, 6])
    def test_a_tree_past_one_hop_still_computes_its_table(self, n: int) -> None:
        """Every row of a table too long to route in single hops.

        The n=5 parity corridor is ~2000 lines against a reach of 255,
        so every 1-arm rides shared rungs across its sibling subtree --
        and a flight that dismounts on the wrong line is a *wrong
        answer* rather than a refusal, which is why the assertion is on
        the output and not on the program building.
        """
        table = "".join(str(bin(row).count("1") & 1) for row in range(2**n))
        program = interprogck8(table)
        assert "<" not in program, "routing must not use the function slot"
        for row in range(2**n):
            bits = list(bin(row)[2:].zfill(n))
            assert run_interprogck8(program, bits) == table[row], f"n={n} row {row}"

    @pytest.mark.parametrize("n", [8, pytest.param(10, marks=pytest.mark.slow)])
    def test_a_high_arity_table_is_computed_row_by_row(self, n: int) -> None:
        """The lifted ceiling, held by execution on hash-picked rows.

        Running all 1024 rows again on every suite run buys nothing over
        a fixed sample once the full sweep has passed, so the rows are
        drawn deterministically from the table's own digest -- plus the
        two ends, where an off-by-one in the printers would land.
        """
        table = _dense_table(n)
        program = interprogck8(table)
        digest = hashlib.sha256(f"rows:{n}".encode()).digest()
        rows = {0, 2**n - 1}
        rows.update(int.from_bytes(digest[i : i + 2]) % 2**n for i in range(0, 32, 2))
        for row in sorted(rows):
            bits = list(bin(row)[2:].zfill(n))
            assert run_interprogck8(program, bits) == table[row], f"n={n} row {row}"

    def test_every_flight_dismounts_on_its_own_stop(self) -> None:
        """The corridor property, pinned on the assembled artifact.

        :func:`_validate` walks each recorded flight over the emitted
        lines exactly as ``DownAccLines`` flies it; parity at n=5 has
        flights crossing whole subtrees and they all land.
        """
        table = "".join(str(bin(row).count("1") & 1) for row in range(32))
        lines, flights = _assemble(table, 5)
        assert flights, "a routed tree records its flights"
        _validate(lines, flights)
