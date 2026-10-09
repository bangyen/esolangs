"""Boolfuck shared-residual regressions."""

import pytest


@pytest.mark.medium
def test_shared_residual_executes_within_ledger() -> None:
    from esolangs.tools.boolfuck import _boolfuck_tree
    from scripts.screens.canonical import corpus
    from tests.generator_support import assert_shared_program

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
