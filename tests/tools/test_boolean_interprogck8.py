"""Unit tests for the Interprogck8 boolean generator.

Every claim here is made by running the emitted program: the tree is
routed by ``DownAccLines``, whose off-by-one is the whole construction, so
reading the source proves nothing about where a branch lands.
"""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.interprogck8 import _Machine
from esolangs.tools.boolean import interprogck8
from esolangs.tools.boolean.interprogck8 import MAX_INPUTS, _set_acc
from esolangs.vm import run_until_halt_or_cycle
from tests.tools.boolean_runners import run_interprogck8


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


class TestArityCap:
    def test_four_inputs_is_refused_with_a_reason(self) -> None:
        """The cap is enforced, not merely documented."""
        with pytest.raises(ValueError, match="at most 3 inputs"):
            interprogck8("0" * 16)

    def test_the_cap_is_the_construction_and_not_the_language(self) -> None:
        """Three inputs place; the failure above it is a jump-reach bound.

        Recorded as a number so a later widening has something to beat: the
        n=3 program is under a thousand lines and every hop inside it is
        under the 255 one ``DownAccLines`` can spell.
        """
        assert MAX_INPUTS == 3
        assert len(interprogck8("01101001").splitlines()) < 1000


class TestLoader:
    @pytest.mark.parametrize("value", [0, 1, 8, 10, 48, 49, 99, 255])
    def test_set_acc_lands_on_its_target(self, value: int) -> None:
        """Executed, not counted: the loader may count up or overshoot."""
        program = "\n".join([*_set_acc(value), "div"])
        assert run_interprogck8(program, []) == chr(value)

    def test_overshooting_is_taken_when_it_is_shorter(self) -> None:
        """8 costs four lines counting back, nine counting up."""
        assert len(_set_acc(8)) == 4
