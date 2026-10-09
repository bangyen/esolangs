"""SStack generator tests."""

import pytest

import esolangs
from esolangs import tools as boolean
from tests.tools.boolean_runners import run_sstack


def test_every_two_input_table_on_every_row() -> None:
    for code in range(16):
        table = f"{code:04b}"
        program = boolean.sstack(table)
        for row in range(4):
            assert run_sstack(program, list(f"{row:02b}")) == table[row], table


def test_a_full_tree_is_28_characters_a_node_and_3_a_leaf() -> None:
    """O(T): 28(T - 1) + 3T + 12 for the prologue, parity folds nothing."""
    for n in (1, 4, 6):
        parity = "".join(str(r.bit_count() % 2) for r in range(1 << n))
        assert len(boolean.sstack(parity)) == 31 * (1 << n) - 16


def test_a_constant_subtree_still_reads_its_inputs() -> None:
    """The fold drops branches, never reads: a trailing read sees the next byte."""
    program = boolean.sstack("0" * 8 + "01" * 4)
    assert program.count(";d;") == 5  # 3 folded, 2 at nodes whose halves agree
    stdin = esolangs.encode_inputs("SStack", [0, 1, 1, 0]) + "B"
    assert esolangs.run("SStack", program + ";e;:e:", stdin=stdin) == "0B"


def test_the_program_is_only_sstack_glyphs() -> None:
    for table in ("10", "0110", "0001", "1" * 8):
        assert set(boolean.sstack(table)) <= set('"0123456789/;[]\\+~:abcd'), table


@pytest.mark.medium
def test_shared_residual_executes_within_ledger() -> None:
    from esolangs.interpreters.stack_based.sstack import _parse
    from esolangs.tools.sstack import _sstack_tree
    from tests.generator_support import assert_shared_program

    a, b = "0001" * 16, "0110" * 16
    table = a + b + b + a
    plain, _ = _sstack_tree(table)
    assert_shared_program(
        "SStack",
        table,
        plain,
        59,
        lambda p: 6 * 8 + 12 + len(_parse(p)).bit_length() + (8).bit_length(),
    )
