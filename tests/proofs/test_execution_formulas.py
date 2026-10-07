"""The Execution column's command formulas hold at small n, over every row.

Each was derived from its generator, not fitted: a fit from parity data
(brainfuck 69n + 41) was beaten by random tables, 458 > 455 at n=6.  An
``exact`` formula must also be reached here; ``bound`` only never exceeded.
"""

import random
from collections.abc import Callable

import pytest

import esolangs
from esolangs.debugger import make_vm
from tests.proofs._ledger import load as load_ledger
from tests.proofs.deep.execution import _dense
from tests.tools.test_boolean_contract import _parity

#: Generator -> (formula in n, exact?, arities checked).  Mirrors the ledger.
FORMULAS: dict[str, tuple[Callable[[int], int], bool, tuple[int, ...]]] = {
    "Container": (lambda n: 2 * n + 2, True, (3, 7)),
    "Fish": (lambda n: 9 * n + 9, True, (3, 6)),
    "Line": (lambda n: 5 * n, True, (3, 5)),
    "Decleq": (lambda n: 49 * n + 3 * 2 ** (2 * n - 1).bit_length() + 2, True, (3, 6)),
    "Qoibl": (lambda n: n + 2, True, (3, 6)),
    "RAM0": (lambda n: n * n + 8 * n + 5, True, (3, 6)),
    "Algebraic Programming Language": (lambda n: (65 * n + 1) // 2 - 21, True, (3, 6)),
    "Alight": (lambda n: 2 * n + 5, True, (3, 6)),
    "BF-PDA": (lambda n: 10 * n + 2, True, (3, 6)),
    "BrainIf": (lambda n: 4 * n + 50, True, (3, 6)),
    "Boolfuck": (lambda n: 2 * n * n + 27 * n + 8, True, (3, 6)),
    "Crement": (lambda n: 5 * n + 2, True, (3, 6)),
    "Factor": (lambda n: 265 * n + 231, True, (4,)),
    "Forbin": (lambda n: 2 * max(n - 7, 0) + 2, True, (3, 8)),
    "Inject": (lambda n: 8 * n + 10, True, (5, 6)),
    "BFStack": (lambda n: 60 * n + 475, False, (8,)),
    "Painfuck": (lambda n: 2 * n * n + 21 * n + 5, False, (3, 6)),
    "Smallfuck": (lambda n: 9 * n * n + 100 * n + 20, False, (3, 6)),
    "Underload": (lambda n: 14 * n + 4, False, (3, 6)),
    "FALSE": (lambda n: 12 * n + 71, False, (3, 6)),
    "Jaune": (lambda n: 10 * n + 7, False, (3, 6)),
}


def _seeded(n: int, seed: int) -> str:
    """A seeded random table; seeds 1 and 3 reach Boolfuck's and BF-PDA's worst."""
    width = 1 << n
    return f"{random.Random(7919 * seed + n).getrandbits(width):0{width}b}"


def _worst(name: str, table: str) -> int:
    """Most commands to halt over every halting row of ``table``."""
    facts = esolangs.describe(name)
    halts = None
    if facts["answer_mode"] == "termination":
        halts = str(list(facts["answer_encoding"]).index("halts"))
    n = len(table).bit_length() - 1
    program = esolangs.generate(name, table)
    worst = 0
    for row in range(len(table)):
        if halts is not None and table[row] != halts:
            continue
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
        if facts["parameterized"]:
            source, stdin = esolangs.instantiate(name, program, bits), ""
        else:
            source, stdin = (
                program,
                esolangs.encode_inputs(name, bits, truth_table=table),
            )
        machine = make_vm(name, source, stdin=stdin)
        steps = 0
        while not machine.halted:
            machine.step()
            steps += 1
        worst = max(worst, steps)
    return worst


@pytest.mark.medium
@pytest.mark.parametrize("name", sorted(FORMULAS))
def test_the_execution_formula_holds(name: str) -> None:
    formula, exact, arities = FORMULAS[name]
    for n in arities:
        tables = (_parity(n), _dense(n), _seeded(n, 1), _seeded(n, 3), "0" * (1 << n))
        worst = max(_worst(name, table) for table in tables)
        assert worst <= formula(n), f"{name} n={n}: {worst} > {formula(n)}"
        if exact:
            assert worst == formula(n), (
                f"{name} n={n}: {worst} never reaches {formula(n)}"
            )


def test_every_formula_cell_is_checked() -> None:
    """A ``worst`` or ``at most`` Execution clause has a formula here, and back."""
    stated = {
        row.generator
        for row in load_ledger().rows
        if row.execution_clause.startswith(("worst ", "at most "))
    }
    assert stated == set(FORMULAS)
