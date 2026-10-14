"""Boolfuck shared-residual regressions."""

import pytest


@pytest.mark.parametrize("table", ["01101001", "00000000"])
def test_program_stays_within_the_command_bound(table) -> None:
    import esolangs
    from esolangs.debugger import make_vm
    from esolangs.languages.boolfuck.generator import _command_bound, boolfuck

    program, bound = boolfuck(table), _command_bound(3)
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
def test_multiple_residuals_reduce_guarded_parity_within_ledger() -> None:
    from esolangs.languages.boolfuck.generator import _boolfuck_tree
    from tests.support.generator_support import assert_shared_program

    n = 10
    residual = "".join(str(row.bit_count() & 1) for row in range(1 << (n - 4)))
    table = "0" * (15 * len(residual)) + residual
    plain, _ = _boolfuck_tree(table)
    assert_shared_program(
        "Boolfuck",
        table,
        plain,
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
