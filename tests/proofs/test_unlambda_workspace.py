"""Unlambda's workspace grows faster than its program."""

import random

import pytest

import esolangs
from esolangs.debugger import make_vm
from scripts.benchmark import WrittenState
from tests.proofs.deep.execution import run_to_answer
from tests.proofs.test_workspace_formulas import FORMULAS
from tests.witness_tables import row_bits


def _unlambda_chain(n: int) -> str:
    """X then a staircase, twice: the root binds X, then a chain of levels."""
    k = n - 2
    x = f"{random.Random(1).getrandbits(1 << k):0{1 << k}b}"

    def chain(flip: int) -> str:
        return str(flip) + "".join(
            str((j + flip) % 2) * (1 << (j - 1)) for j in range(1, k + 1)
        )

    return x + chain(0) + x + chain(1)


@pytest.mark.medium
def test_unlambda_workspace_is_not_linear() -> None:
    """Every 0-selected level keeps a copy of the share: peak/L grows with n."""
    formula = FORMULAS["Unlambda"][0]
    per_char = []
    for n in (5, 7):
        table = _unlambda_chain(n)
        program = esolangs.generate("Unlambda", table)
        row = 1 << (n - 2)  # inputs 0, 1, 0, ..., 0: down X's zero path
        bits = row_bits(row, n)
        stdin = esolangs.encode_inputs("Unlambda", bits, truth_table=table)
        machine = make_vm("Unlambda", program, stdin=stdin)
        state = WrittenState(machine.snapshot())
        run_to_answer(machine, sample=state.sample)
        assert state.bits <= formula(n, program)
        per_char.append(state.bits / len(program))
    # Measured 7.58 then 16.60; a linear workspace would hold it flat.
    assert per_char[1] > 1.5 * per_char[0], per_char
