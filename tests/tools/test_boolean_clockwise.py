"""Covers :mod:`esolangs.tools.clockwise`."""

import pytest

from esolangs import tools as boolean
from tests.interpreters.clockwise_observer import Factory


class TestClockwise:
    def test_the_table_is_one_cell_per_entry(self) -> None:
        """The construction's signature: the answer row holds the table itself.

        A tree spends a node per level per leaf; this spends one ``+`` per
        set entry on a single row, and the countdown row above it one ``!``
        per entry whatever the table says.  Flipping one row of the table
        therefore moves exactly one character, which is what says the table
        is stored rather than routed.
        """
        n = 5
        size = 1 << n
        table = ["0"] * size
        base = boolean.clockwise("".join(table))
        for entry in (0, 1, 7, size - 1):
            table[entry] = "1"
            flipped = boolean.clockwise("".join(table))
            table[entry] = "0"
            differ = [
                (row, col)
                for row, (before, after) in enumerate(
                    zip(base.splitlines(), flipped.splitlines(), strict=True)
                )
                for col, (old, new) in enumerate(
                    zip(before.ljust(len(after)), after, strict=True)
                )
                if old != new
            ]
            assert len(differ) == 1, (entry, differ)
            assert flipped.splitlines()[differ[0][0]][differ[0][1]] == "+"

    def test_size_is_linear_in_the_table(self) -> None:
        """Four table rows and a doubling chain: both linear, so size is.

        The chain's gadgets double in width as the level rises, so the whole
        chain costs a constant times its top gadget; the table costs its five
        rows.  Doubling the table therefore roughly doubles the program,
        which a tree's per-level rows would not do.
        """
        sizes = [len(boolean.clockwise("01101001" * (2 ** (n - 3)))) for n in (5, 7, 9)]
        rise = (sizes[2] - sizes[1]) / (sizes[1] - sizes[0])
        assert 3.5 < rise < 4.4, sizes
        assert sizes[2] / 2**9 < 20, sizes


@pytest.mark.medium
@pytest.mark.parametrize("width", [1, 2, 3, 9, 10, 11, 20, 27, 80])
def test_width_rotates_the_lookup_without_changing_answers(width: int) -> None:
    """Both lookup orientations execute every row, including floor widths."""
    import esolangs

    for n in range(1, 7):
        table = ("01101001" * 8)[: 1 << n]
        plain = boolean.clockwise(table)
        program = esolangs.generate("Clockwise", table, width)
        plain_width = max(map(len, plain.splitlines()))
        assert max(map(len, program.splitlines())) <= max(
            width, min(plain_width, 2 if n <= 2 else 2 * n + 5)
        )
        if plain_width <= width:
            assert program == plain
        factory = Factory(program.splitlines())
        for combo in range(1 << n):
            assert factory.check(format(combo, f"0{n}b"), table[combo])["halted"]


def test_rotated_lookup_size_is_linear() -> None:
    """Implicit padded rails keep rotation from rendering a filled rectangle."""
    sizes = [len(boolean.clockwise("01101001" * (2 ** (n - 3)), 1)) for n in (5, 7, 9)]
    assert sizes[2] / 2**9 < 30
    assert 3.5 < (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) < 4.4


def test_single_column_cannot_close_a_clockwise_ring() -> None:
    """A downward beam's next clockwise turn leaves the only column."""
    from esolangs.interpreters.grid_based.clockwise import _Machine
    from esolangs.interpreters.io import ScriptedIO

    machine = _Machine(["R", "R"], ScriptedIO(""))
    machine.step()
    machine.step()
    with pytest.raises(ValueError, match="ring is not closed"):
        machine.step()
    assert len(boolean.clockwise("0110", 1)) == 112
