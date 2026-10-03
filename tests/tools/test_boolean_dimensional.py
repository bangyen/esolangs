"""Dimensional generator tests."""

import pytest

from esolangs import tools as boolean
from esolangs.tools.dimensional import dimensional


@pytest.mark.parametrize("width", [None, 2, 3, 8, 80])
def test_other_widths_preserve_the_established_build(width: int | None) -> None:
    from esolangs.tools.wrap import wrap_program

    for table in ("00", "11", "0110", "0001", "10010110"):
        assert dimensional(table, width) == wrap_program(
            dimensional(table), "dimensional", width
        )


class TestDimensional:
    def test_a_bare_move_is_the_addressing(self) -> None:
        """A bare >/< takes its dimension from the cell, which is the point.

        One per read -- ``d>`` steps along dimension 1 for a one bit and 0
        for a zero -- and one per painted one-cell, whose ``+`` leaves the
        1 the following ``>`` reads.  ``0110`` paints as far as its last
        one at index 2, so that is two reads and one one-cell before it.
        """
        program = boolean.dimensional("0110")
        bare = [
            i
            for i, c in enumerate(program)
            if c in "><" and not program[i + 1 :][:1].isdigit()
        ]
        assert len(bare) == 3, program

    def test_the_table_costs_two_characters_an_entry(self) -> None:
        """One painted cell an entry, whichever bit it is.

        A zero-cell steps with ``>1`` and a one-cell with ``+`` and a bare
        ``>``; both are two characters, so the emitted length does not
        carry the table's contents.
        """
        full = "1" * 64
        one = "0" * 63 + "1"
        assert len(boolean.dimensional(full)) == len(boolean.dimensional(one))
        parity = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(64))
        assert len(boolean.dimensional(parity)) < 10_000

    def test_a_sparse_table_pays_only_for_its_prefix(self) -> None:
        """An unvisited cell already reads 0, so painting stops at the last one."""
        early = "1" + "0" * 15
        late = "0" * 15 + "1"
        assert len(boolean.dimensional(early)) < len(boolean.dimensional(late))


class TestGeneratorEdgePaths:
    def test_dimensional_validation(self) -> None:
        """The Dimensional generator rejects bad truth tables."""
        with pytest.raises(ValueError, match="power-of-two"):
            boolean.dimensional("011")
        with pytest.raises(ValueError, match="only '0' and '1'"):
            boolean.dimensional("0123")
