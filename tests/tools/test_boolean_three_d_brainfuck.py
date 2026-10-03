"""three_d_brainfuck generator tests."""

from esolangs import tools as boolean


class TestThreeDBf:
    def test_a_constant_zero_side_needs_no_flag(self) -> None:
        """Pin the three-input total: 35,488 characters before, 28,734 after.

        A node whose zero-side is constant adds it up front and keeps only
        the bit's loop, so AND is two nested loops; the run starts on the
        multiplier rather than walking to it.
        """
        assert boolean.three_d_brainfuck("0001").endswith("e[-n[-e+w]s]ne.")
        tables = [f"{value:08b}" for value in range(256)]
        assert sum(len(boolean.three_d_brainfuck(t)) for t in tables) == 28734
