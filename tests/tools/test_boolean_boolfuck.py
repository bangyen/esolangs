"""Boolfuck shared-residual regressions."""

import random

import pytest


@pytest.mark.medium
def test_shared_residual_executes_within_ledger() -> None:
    from esolangs.tools.boolfuck import _boolfuck_tree
    from tests.generator_support import assert_shared_program
    from tests.screen_support import corpus

    table = corpus(8)["tiled"]
    plain, _ = _boolfuck_tree(table)
    assert_shared_program(
        "Boolfuck",
        table,
        plain,
        352,
        lambda p: (
            (len(p) - 1).bit_length()
            + max(12, (2 * 8 - 2).bit_length() + 10)
            + 8
            + sum(i.bit_length() for i in range(8))
            + (2 * 8).bit_length()
            + (8).bit_length()
        ),
    )


@pytest.mark.parametrize(
    ("table", "shared"), [("01101001", (0, 0)), ("00000000", (1, 0))]
)
def test_dispatch_accounts_for_a_single_reachable_path_class(table, shared) -> None:
    import esolangs
    from esolangs.debugger import make_vm
    from esolangs.tools.boolfuck import _boolfuck_tree

    program, bound = _boolfuck_tree(table, shared)
    for row, expected in enumerate(table):
        machine = make_vm("Boolfuck", program, stdin=f"{row:03b}")
        commands = 0
        while not machine.halted and commands <= bound:
            machine.step()
            commands += 1
        assert machine.halted
        assert commands <= bound
        assert esolangs.read_answer("Boolfuck", machine.output) == expected


@pytest.mark.medium
def test_multiple_residual_dispatches_match_outputs_and_command_prices():
    import esolangs
    from esolangs.debugger import make_vm
    from esolangs.tools.boolfuck import _boolfuck_tree
    from esolangs.tools.shared_block import repeated_blocks

    rng = random.Random(722026)
    tables = ["".join(str(rng.randrange(2)) for _ in range(64)) for _ in range(12)]
    tables.append("0" * 224 + "01101001" * 4)
    served = 0
    for table in tables:
        n = len(table).bit_length() - 1
        blocks = repeated_blocks(table)
        served += len(blocks) > 1
        program, limit = _boolfuck_tree(table, shared_blocks=blocks)
        for row, expected in enumerate(table):
            machine = make_vm("Boolfuck", program, stdin=f"{row:0{n}b}")
            commands = 0
            while not machine.halted and commands <= limit:
                machine.step()
                commands += 1
            assert machine.halted
            assert esolangs.read_answer("Boolfuck", machine.output) == expected
            assert commands <= limit
    assert served > 0


@pytest.mark.medium
def test_multiple_residuals_reduce_guarded_parity_within_ledger():
    from esolangs.tools.boolfuck import _boolfuck_tree
    from esolangs.tools.shared_block import repeated_block
    from tests.generator_support import assert_shared_program

    n = 10
    residual = "".join(str(row.bit_count() & 1) for row in range(1 << (n - 4)))
    table = "0" * (15 * len(residual)) + residual
    previous, _ = _boolfuck_tree(table, repeated_block(table))
    assert_shared_program(
        "Boolfuck",
        table,
        previous,
        2 * n * n + 27 * n + 8,
        lambda p: (
            (len(p) - 1).bit_length()
            + max(12, (2 * n - 2).bit_length() + 10)
            + 8
            + sum(i.bit_length() for i in range(n))
            + (2 * n).bit_length()
            + n.bit_length()
        ),
        rows=[
            *range(15 * len(residual), len(table)),
            *[prefix * len(residual) + len(residual) - 1 for prefix in range(15)],
        ],
    )
