"""rotfuck generator tests."""

import pytest

from esolangs import tools as boolean
from tests.tools.boolean_runners import (
    run_rotfuck,
)


class TestRotfuck:
    """The ROTfuck boolean generator.

    ROTfuck rotates the program after every command, so a loop only works if
    its every pass reads the same commands: the generator pins each loop's
    cycle to 0 (mod 8) and reaches its back-jump target through a phantom
    that is never executed.  On that it builds a tape lookup -- the table in
    the even cells, a variable-distance pointer walk over the odd ones.
    """

    def test_every_pad_is_invisible_and_they_are_shortest_first(self) -> None:
        """Padding shifts the rotation without shifting anything else.

        A pad is what moves a command off a rotation where it would read as
        a bracket, so it has to leave every cell and the pointer where it
        found them -- and never step left of where it started, because
        ``<`` clamps at cell zero and a pad that reached past the caller's
        cell would not be neutral there.  Length runs shortest first, since
        padding is pure cost.
        """
        from esolangs.tools.rotfuck import _PADS

        assert _PADS[0] in ("+-", "-+", "><")
        assert list(_PADS) == sorted(_PADS, key=len)
        for pad in _PADS:
            cells: dict[int, int] = {}
            at = low = 0
            for char in pad:
                assert char in "+-><", pad
                at += (char == ">") - (char == "<")
                low = min(low, at)
                cells[at] = cells.get(at, 0) + (char == "+") - (char == "-")
            assert at == 0, pad
            assert low == 0, pad
            assert not any(cells.values()), pad

    @pytest.mark.parametrize("trips", range(7))
    def test_a_loop_leaves_the_rotation_where_it_found_it(self, trips: int) -> None:
        """The invariant every loop rests on, checked by running one.

        A loop's trip count is data, so the rotation it exits at must not
        depend on it -- otherwise every command after the loop means
        something else for a different input.  The generator gets that by
        padding each loop's cycle to 0 (mod 8).  Here a drain loop runs
        ``trips`` times and the *same* trailing ``+`` run and ``.`` follow
        it: if the exit rotation moved with the trip count, that tail would
        not still be a print of the right character.
        """
        from esolangs.tools.helpers import _ASCII_ZERO
        from esolangs.tools.rotfuck import _Builder

        out = _Builder()
        out.travel(2)
        out.emit("+" * trips)
        out.travel(4)
        out.drain("-<<+>>>>++")
        out.travel(0)
        out.emit("+" * _ASCII_ZERO)
        out.emit(".")
        assert run_rotfuck(out.text(), []) == str(trips)

    def test_the_program_is_only_command_characters(self) -> None:
        """Nothing but the eight commands is emitted.

        ROTfuck treats a character outside its alphabet as a comment that
        neither executes *nor advances the rotation*, so stray text is
        invisible to any behavioural check -- a program with padding
        between every command computes the same table.  The alphabet is
        therefore asserted directly rather than inferred from the answer.
        """
        for table in ("01", "0110", "11110000", "01101001"):
            assert set(boolean.rotfuck(table)) <= set("+-><,.[]"), table

    @pytest.mark.parametrize(
        ("table", "length"),
        [
            ("01", 224),
            ("10", 224),
            ("0001", 390),
            ("0110", 391),
            ("11110000", 228),
            ("01101001", 571),
        ],
    )
    def test_the_emitted_length_is_exact(self, table: str, length: int) -> None:
        """The layout is deterministic down to the character.

        Several ways of getting this wrong leave a *correct* program: a
        pad taken at four characters where two would have hidden, a cycle
        padded to 8 (mod 8) rather than 0 (which is the same rotation and
        so still runs), or a travel that walks the pointer home when it is
        already there.  None of them changes an answer, and a loose size
        bound only catches them by luck, so the lengths are pinned.

        ``11110000`` also carries dependency reduction: it lays out a
        two-entry table, 228 characters against ``01101001``'s 571.
        """
        assert len(boolean.rotfuck(table)) == length


def test_rotfuck_loop_does_not_swallow_an_invariant_failure() -> None:
    from esolangs.tools.rotfuck import _Builder

    def broken() -> None:
        raise AssertionError("broken body invariant")

    with pytest.raises(AssertionError, match="broken body invariant"):
        _Builder().loop(broken, lambda: None)
