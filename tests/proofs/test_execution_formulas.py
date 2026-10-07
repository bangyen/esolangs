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
from scripts.benchmark import WrittenState
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
    "brainfuck": (lambda n: 69 * n + 44, True, (3, 6)),
    "Circuit Diagram": (lambda n: 2 * n + 1 + (n >= 8), True, (3, 8)),
    "Forbin": (lambda n: 2 * max(n - 7, 0) + 2, True, (3, 8)),
    "Inject": (lambda n: 8 * n + 10, True, (5, 6)),
    "BFStack": (lambda n: 60 * n + 475, True, (8,)),
    # Proved for all n: a path costs at most the all-ones one, and a
    # level's moves at most max(a, b) + 2 over adjacent input cells a, b.
    "Painfuck": (lambda n: -(-3 * n * n // 4) + 20 * n + 4, False, (3, 6)),
    "Smallfuck": (lambda n: 9 * n * n + 100 * n + 20, False, (3, 6)),
    "Underload": (lambda n: 14 * n - 1, False, (3, 6)),
    "FALSE": (lambda n: min(12 * n + 69, 10 * n + 99), False, (3, 6)),
    "Jaune": (lambda n: 8 * n - 2, False, (3, 6)),
}


def _seeded(n: int, seed: int) -> str:
    """A seeded random table; seeds 1 and 3 reach Boolfuck's and BF-PDA's worst."""
    width = 1 << n
    return f"{random.Random(7919 * seed + n).getrandbits(width):0{width}b}"


#: BFStack's worst 7-input block, a rule: 64 zeros, 60 ones, a zero, then ones.
_BFSTACK_BLOCK = "0" * 64 + "1" * 60 + "0" + "111"


def _tables(name: str, n: int) -> tuple[str, ...]:
    """Parity, dense, two seeded, constants, AND, alternating, NAND, ends."""
    width = 1 << n
    if name == "Circuit Diagram" and n >= 8:
        # Its worst, the all-ones H-layout; a wide circuit parses in 0.7s.
        return ("1" * width,)
    if name == "LaserFuck" and n >= 5:
        # Its worst is all zeros; a 3T + 1 cell tape snapshots every step.
        return (_parity(n), _dense(n), "0" * width)
    tables = (
        _parity(n),
        _dense(n),
        _seeded(n, 1),
        _seeded(n, 3),
        "0" * width,
        "1" * width,
        "0" * (width - 1) + "1",
        "10" * (width // 2),
        "1" * (width - 1) + "0",
        "1" + "0" * (width - 2) + "1",
    )
    if name == "BFStack" and n >= 7:
        tables += (_BFSTACK_BLOCK * (1 << (n - 7)),)
    return tables


def _worst(name: str, table: str, *, written: bool = False) -> int:
    """Most commands to halt, or ``written`` state bits, over halting rows."""
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
        state = WrittenState(machine.snapshot())
        steps = 0
        while not machine.halted:
            machine.step()
            steps += 1
            if written:
                state.sample(machine.snapshot())
        worst = max(worst, state.bits if written else steps)
    return worst


@pytest.mark.medium
@pytest.mark.parametrize("name", sorted(FORMULAS))
def test_the_execution_formula_holds(name: str) -> None:
    formula, exact, arities = FORMULAS[name]
    for n in arities:
        worst = max(_worst(name, table) for table in _tables(name, n))
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
