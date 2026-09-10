"""Unit tests for the Interprogck8 generators, boolean and text.

Every claim here is made by running the emitted program: the tree is
routed by ``DownAccLines``, whose off-by-one is the whole construction, so
reading the source proves nothing about where a branch lands.
"""

import hashlib
import importlib

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.interprogck8 import _Machine, run
from esolangs.tools.boolean import interprogck8
from esolangs.tools.boolean.interprogck8 import (
    _REACH,
    _check,
    _emit,
    _index,
    _Jump,
    _place,
    _route,
    _set_acc,
    _settle,
)
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
    @pytest.mark.parametrize("n", [1, 2, 3])
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
        """A constant subtree drops its branch, not its reads.

        The reads are the interface: leaving a bit unread desynchronises
        whatever runs on the same stream next.
        """
        program = interprogck8(table)
        io = ScriptedIO("0\n1\n1\n")
        machine = _Machine(program.splitlines(), io)
        run_until_halt_or_cycle(machine)
        assert io.position() == 3, "a constant table must still read all three"
        assert io.getvalue() == table[0b011]


class TestExpress:
    """Past n=3 the tree outgrows one hop, so hops ride the express."""

    @pytest.mark.parametrize("n", [4, 5, 6])
    def test_a_tree_past_one_hop_still_computes_its_table(self, n: int) -> None:
        """Every row of a table too long to route in single hops.

        This is what the arity cap used to refuse.  The n=5 parity tree is
        ~2900 lines with crossings of over 1000 against a reach of 255, so
        it only works if the express relays -- and a rung that carries a
        chain to the wrong place is a *wrong answer* rather than a
        refusal, which is why the assertion is on the output and not on
        the program building.
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

        n=10 dense is ~92k lines and a few seconds to build; running all
        1024 rows again on every suite run buys nothing over a fixed
        sample once the full sweep has passed, so the rows are drawn
        deterministically from the table's own digest -- plus the two
        ends, where an off-by-one in the ladder would land.
        """
        table = _dense_table(n)
        program = interprogck8(table)
        lines = program.splitlines()
        digest = hashlib.sha256(f"rows:{n}".encode()).digest()
        rows = {0, 2**n - 1}
        rows.update(int.from_bytes(digest[i : i + 2]) % 2**n for i in range(0, 32, 2))
        for row in sorted(rows):
            bits = list(bin(row)[2:].zfill(n))
            assert run_interprogck8("\n".join(lines), bits) == table[row], (
                f"n={n} row {row}"
            )

    def test_a_table_the_meadows_cannot_carry_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Starved of rung space, routing refuses rather than mis-lands.

        Meadows two lines wide hold no usable rung, and a repair budget of
        zero may not add more -- so the only correct outcome is the
        refusal that names the stranded window.  What must not happen is
        a program that routes through the wrong place, or a hang.
        """
        table = _dense_table(6)
        # By name: the package re-exports the generator under the module's
        # own name, so a plain import binds the function, not the module.
        module = importlib.import_module("esolangs.tools.boolean.interprogck8")
        with monkeypatch.context() as patch:
            patch.setattr(module, "_MEADOW_LEAST", 2)
            patch.setattr(module, "_MEADOW_MOST", 2)
            patch.setattr(module, "_REPAIRS", -1)
            with pytest.raises(ValueError, match="no rung slot"):
                interprogck8(table)
        # ...and the real meadows still build the same table.
        assert interprogck8(table)

    def test_every_hop_in_a_routed_program_is_inside_the_reach(self) -> None:
        """The routing leaves no jump the gadget cannot spell.

        The emission pass would raise on one, so this pins the property the
        raise defends rather than re-testing the raise: after routing, every
        distance is within a single ``DownAccLines``.
        """
        parity = "".join(str(bin(row).count("1") & 1) for row in range(32))
        items = _emit(parity, 5)
        _settle(items)
        meadows = _place(items)
        _settle(items)
        assert _route(items, meadows) == [], "parity at n=5 routes unrepaired"
        starts, labels = _index(items)
        for item, start in zip(items, starts, strict=True):
            if isinstance(item, _Jump):
                goal = item.to_line if item.to_line is not None else labels[item.label]
                distance = goal - (start + item.width)
                assert 0 <= distance <= _REACH, f"{item.label} spans {distance}"


class TestJumpChecks:
    """The two guards that keep an over-long jump from being emitted."""

    def test_a_jump_past_the_reach_is_refused(self) -> None:
        with pytest.raises(ValueError, match="spans 300 lines"):
            _check("X", 300, 40)

    def test_a_jump_too_wide_for_its_slot_is_refused(self) -> None:
        """The fixed window is what this protects: it cannot grow."""
        with pytest.raises(ValueError, match="needs 10 lines, has 9"):
            _check("X", 36, 9)


class TestLoader:
    @pytest.mark.parametrize("value", [0, 1, 8, 10, 48, 49, 99, 255])
    def test_set_acc_lands_on_its_target(self, value: int) -> None:
        """Executed, not counted: the loader may count up or overshoot."""
        program = "\n".join([*_set_acc(value), "div"])
        assert run_interprogck8(program, []) == chr(value)

    def test_overshooting_is_taken_when_it_is_shorter(self) -> None:
        """8 costs four lines counting back, nine counting up."""
        assert len(_set_acc(8)) == 4


