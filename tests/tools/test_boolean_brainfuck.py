"""brainfuck generator tests."""

import random

import pytest

from esolangs.tools.brainfuck import bf_tree


class TestBfTree:
    def test_parity_table_is_unfolded(self) -> None:
        """A table with no constant subtree still spends a leaf per row."""
        xor3 = "10010110"
        assert bf_tree(xor3).count("[-") == 14
        assert bf_tree("11110000").count("[-") == 2


@pytest.mark.medium
def test_shared_residual_executes_within_ledger() -> None:
    from esolangs.tools.brainfuck import _bf_ordered
    from tests.generator_support import assert_shared_program

    zero = "0001011101101001" * 4
    one = "0110100100010111" * 4
    table = zero + one + one + zero
    plain = _bf_ordered(table, tuple(range(8)), share=False)
    assert_shared_program(
        "brainfuck",
        table,
        plain,
        69 * 8 + 44,
        lambda p: (
            2 * 8 + 6 + (2 * 8).bit_length() + (8).bit_length() + len(p).bit_length()
        ),
    )


@pytest.mark.medium
def test_multiple_residual_dispatches_match_outputs_and_command_prices():
    from esolangs.debugger import make_vm
    from esolangs.tools.shared_block import repeated_blocks
    from esolangs.tools.shared_flag import flag_tree_body

    rng = random.Random(722026)
    tables = ["".join(str(rng.randrange(2)) for _ in range(64)) for _ in range(12)]
    tables.append("0" * 224 + "01101001" * 4)
    served = 0
    for table in tables:
        n = len(table).bit_length() - 1
        blocks = repeated_blocks(table)
        served += len(blocks) > 1
        body, cost = flag_tree_body(
            table, tuple(range(n)), 2 * (n - 1), 2 * n, shared_blocks=blocks
        )
        header = ">>".join("," + "-" * 48 for _ in range(n))
        source = header + body + "+" * 48 + "."
        limit = len(header) + cost + 49
        for row, expected in enumerate(table):
            machine = make_vm("brainfuck", source, stdin=f"{row:0{n}b}")
            commands = 0
            while not machine.halted and commands <= limit:
                machine.step()
                commands += 1
            assert machine.halted
            assert machine.output == expected
            assert commands <= limit
    assert served > 0


@pytest.mark.parametrize("blocks", [((1, 0), (1, 4)), ((2, 0), (1, 0)), ((3, 0),)])
def test_deferred_flags_require_ordered_distinct_levels(blocks):
    from esolangs.tools.shared_flag import flag_tree_body

    with pytest.raises(ValueError, match="deferred levels"):
        flag_tree_body("01101001", (0, 1, 2), 4, 6, shared_blocks=blocks)


@pytest.mark.medium
def test_multiple_residuals_reduce_guarded_parity_within_ledger():
    import esolangs
    from esolangs.tools.shared_block import repeated_block
    from esolangs.tools.shared_flag import flag_tree_body
    from tests.generator_support import assert_shared_program

    n = 10
    residual = "".join(str(row.bit_count() & 1) for row in range(1 << (n - 4)))
    table = "0" * (15 * len(residual)) + residual
    body, _ = flag_tree_body(
        table, tuple(range(n)), 2 * (n - 1), 2 * n, shared=repeated_block(table)
    )
    previous = ">>".join("," + "-" * 48 for _ in range(n)) + body + "+" * 48 + "."
    assert len(esolangs.generate("brainfuck", table)) < len(previous)
    assert_shared_program(
        "brainfuck",
        table,
        previous,
        69 * n + 44,
        lambda p: (
            2 * n + 6 + (2 * n).bit_length() + n.bit_length() + len(p).bit_length()
        ),
        rows=[
            *range(15 * len(residual), len(table)),
            *[prefix * len(residual) + len(residual) - 1 for prefix in range(15)],
        ],
    )
