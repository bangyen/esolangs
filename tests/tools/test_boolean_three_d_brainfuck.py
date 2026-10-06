"""three_d_brainfuck generator tests."""

from esolangs import tools as boolean


class TestThreeDBf:
    def test_array_moves_use_the_3d_axes(self) -> None:
        """3D Brainfuck's >/< are no-ops, so the array moves with e/w."""
        program = boolean.three_d_brainfuck("0110")
        assert ">" not in program
        assert "<" not in program
        assert "e" in program
        assert "w" in program

    def test_a_constant_zero_side_needs_no_flag(self) -> None:
        """Pin the three-input total: 35,488 characters before, 28,734 after."""
        assert boolean.three_d_brainfuck("0001").endswith("e[-n[-e+w]s]ne.")
        tables = [f"{value:08b}" for value in range(256)]
        assert sum(len(boolean.three_d_brainfuck(t)) for t in tables) == 28734
