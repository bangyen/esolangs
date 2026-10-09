"""painfuck generator tests."""

import pytest

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


@pytest.mark.medium
def test_shared_residual_executes_within_ledger() -> None:
    from esolangs.tools.painfuck import _painfuck_tree
    from scripts.screens.canonical import corpus
    from tests.generator_support import assert_shared_program

    table = corpus(8)["tiled"]
    plain, _ = _painfuck_tree(table, tuple(range(8)))
    assert_shared_program(
        "Painfuck",
        table,
        plain,
        212,
        lambda p: 2 * 8 + 5 + 3 * (8).bit_length() + 9 * len(p).bit_length(),
    )
