"""painfuck generator tests."""

from esolangs import tools as boolean


class TestPainfuck:
    def test_commands_are_preshifted_for_the_trans_table(self) -> None:
        """The interpreter shifts commands through its cycles, so the source
        must be the inverse shift; the translated commands are the BF moves."""
        from esolangs.interpreters.tape_based.painfuck import _translate

        program = boolean.painfuck("0110")
        translated = _translate(program)
        assert "a" in translated  # [ loops
        assert "b" in translated  # ] loops
        assert translated.count("a") == translated.count("b")
        assert "rl" in translated or "l" in translated  # pointer moves
