"""Boolfuck shared-residual regressions."""

import pytest


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
def test_multiple_residuals_reduce_guarded_parity_within_ledger():
    from esolangs.tools.boolfuck import _boolfuck_tree
    from esolangs.tools.shared_block import repeated_block
    from tests.support.generator_support import assert_shared_program

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
