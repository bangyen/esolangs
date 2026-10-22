"""The Execution column's command formulas hold at small n, over every row.

Each was derived from its generator, not fitted: a fit from parity data
(brainfuck 69n + 41) was beaten by random tables, 458 > 455 at n=6.  An
``exact`` formula must also be reached here; ``bound`` only never exceeded.
"""

import random
from collections.abc import Callable

import esolangs
from esolangs.debugger import make_vm
from esolangs.registry import LANGUAGES
from scripts.benchmark import WrittenState
from tests.proofs._arities import formula_arities
from tests.proofs._formula import ledger_formulas
from tests.proofs._ledger import load as load_ledger
from tests.proofs.deep.execution import _dense, run_to_answer
from tests.support.generator_support import CHECK
from tests.support.witness_tables import parity as _parity
from tests.support.witness_tables import row_bits

#: Formulas the ledger notation cannot state: a case split, a definition,
#: a count taken from the program.  Each lives on its language's
#: ``proof_execution`` (``proof_formulas.py`` in its package); this table
#: holds only entries that cannot relocate, with the reason.
_HAND: dict[str, tuple[Callable[[int, str], float], bool, tuple[int, ...]]] = {}
#: Arities where the default (see ``ledger_formulas``) is too slow or too
#: shallow for the construction, aggregated from each package's
#: ``[formula_arities]`` section.
_ARITIES = formula_arities("execution")

#: Generator -> (formula, exact?, arities): the ledger's own clause where
#: it parses (``tests/proofs/_formula.py``), else ``_HAND``.
_HAND.update(
    (name, lang.proof_execution)
    for name, lang in LANGUAGES.items()
    if lang.proof_execution is not None
)
FORMULAS = ledger_formulas(
    lambda row: row.execution_clause, _HAND, _ARITIES, column="execution"
)


def _seeded(n: int, seed: int) -> str:
    """A deterministic random table for the formula corpus."""
    width = 1 << n
    return f"{random.Random(7919 * seed + n).getrandbits(width):0{width}b}"


# language-owners: ["BFStack"]
#: BFStack's worst 7-input block, a rule: 64 zeros, 60 ones, a zero, then ones.
_BFSTACK_BLOCK = "0" * 64 + "1" * 60 + "0" + "111"


def _bfstack_worst(n: int) -> str:
    """Worst past n = 7, a rule: the block under classifier nodes.

    Two inputs wrap ``t`` as ``t d d t`` with ``d`` all ones: the classifier
    reads 1001 and its last row costs 146 commands against two branches' 120.
    An odd input goes under an all-ones half.
    """
    table = _BFSTACK_BLOCK
    if n % 2 == 0:
        table = "1" * len(table) + table
    while len(table) < 1 << n:
        table += "1" * len(table) * 2 + table
    return table


def _tables(name: str, n: int) -> tuple[str, ...]:
    """Structured and random tables, with named worst-case witnesses."""
    width = 1 << n
    if name == "Circuit Diagram" and n >= 8:
        # Parity reaches 2n+1 at n=8; dense tables exercise pool admission
        # and constants use only their clock gate.
        return (_seeded(n, 1), _parity(n), "1" * width)
    if name == "Streetcode":
        # Its worst in both columns, n = 6..8: one zero, the last entry.
        return ("1" * (width - 1) + "0",)
    if name == "Malbolge":
        # Straight-line code: all 10 tables tie at every n measured.
        return (_dense(n),)
    if name == "Befunge":
        # Straight-line code over the inputs that matter; parity has all.
        return (_parity(n),)
    if name == "LaserFuck" and n >= 5:
        # Its worsts, all zeros and all ones; a 3T + 1 cell tape is slow.
        return (_parity(n), _dense(n), "0" * width, "1" * width)
    if name == "BFStack" and n >= 10:
        # Lower arities sweep the generic families; this named witness reaches
        # the combined classifier/odd-prefix bound without repeating them.
        return (_bfstack_worst(n),)
    if name == "Algebraic Programming Language" and n >= 8:
        # Lower arities sweep the full corpus; retain shared, dense and inline
        # program shapes for the larger frame/serial bounds.
        return (_parity(n), _dense(n), "0" * width, "1" * width)
    tables = (
        _parity(n),
        _seeded(n, 1),
        "0" * width,
        "1" * width,
        "0" * (width - 1) + "1",
        "10" * (width // 2),
        "1" * (width - 1) + "0",
        "1" + "0" * (width - 2) + "1",
        "01" * (width // 2),
    )
    if name == "BFStack" and n >= 7:
        tables += (_bfstack_worst(n),)
    if name == "AddSubJump":
        # The packed decoder's worst now that the tree takes the lone zero:
        # ones but rows 8 mod 9 and the last, reaching it at n = 6.
        tables += (
            "".join("0" if r % 9 == 8 or r == width - 1 else "1" for r in range(width)),
        )
    if name == "Bitdeque":
        tables += ("10" + "01" * (width // 2 - 1),)
    if name in {"ArrowQueue", "ROTfuck"}:
        # Their worst, exhaustive through n=3: a lone zero, second to last.
        # ROTfuck's was NAND's until symmetric tables took the counted walk.
        tables += ("1" * (width - 2) + "01",)
    if name == "Home Row":
        # Alternating but for one equal pair: every input essential, T - 2 leaves.
        tables += ("10" * (width // 2 - 1) + "01",)
    if name == "Back":
        # Rudin-Shapiro (parity of 11 pairs in the row), complemented at odd n
        # and with row 1 flipped: the most rows its one-edges cannot share.
        tables += (
            "".join(
                str(bin(i & i >> 1).count("1") % 2 ^ n % 2 ^ (i == 1))
                for i in range(width)
            ),
        )
    if name == "Unsquare" and n >= 6:
        # Ends of one cell, runs of 12 and 14 between: 12a + 14b = 2**(n-1) - 1.
        b = (2 ** (n - 1) - 1) % 6
        a = (2 ** (n - 1) - 1 - 7 * b) // 6
        runs = [1, *[12] * (a // 2), *[14] * b, *[12] * (a - a // 2), 1]
        tables += ("".join(str(i % 2) * c for i, c in enumerate(runs)),)
    if name == "Packlang":
        # The most zeros a 128-row fill block may punch, in every block;
        # zeros are isolated, since a run of ones would be a shorter loop.
        block = min(width, 128)
        zeros = (block - 4) // 2
        tail = block - 2 * (zeros - 1)
        # The odd tail zero keeps every input essential.
        head = "10" * (zeros - 1) + "11" + "0" + "1" * (tail - 3)
        # Swap pair j of 16-row block j, so no two blocks are equal: equal
        # ones alias at a smaller block (n=7: 311 steps, not 1205).
        cells = list(head)
        for j in range(block // 16 - 1):
            at = 16 * j + 2 * j % 16
            cells[at], cells[at + 1] = cells[at + 1], cells[at]
        tables += ("".join(cells) * (width // block),)
    return tuple(dict.fromkeys(tables))


def _measure(
    name: str,
    table: str,
    *,
    written: bool = False,
    program: esolangs.Program | None = None,
) -> tuple[int, int]:
    """Most commands and optional written-state bits over halting rows."""
    facts = esolangs.describe(name)
    halts = None
    if facts["answer_mode"] == "termination":
        halts = str(list(facts["answer_encoding"]).index("halts"))
    n = len(table).bit_length() - 1
    if program is None:
        program = esolangs.generate(name, table)
    worst_steps = worst_bits = 0
    for row in range(len(table)):
        if halts is not None and table[row] != halts:
            continue
        bits = row_bits(row, n)
        if facts["parameterized"]:
            source, stdin = esolangs.instantiate(name, program, bits), ""
        else:
            source, stdin = (
                program,
                esolangs.encode_inputs(name, bits, truth_table=table),
            )
        machine = make_vm(name, source, stdin=stdin)
        state = WrittenState(machine.snapshot()) if written else None
        steps = run_to_answer(
            machine, sample=state.sample if state is not None else None
        )
        assert steps is not None  # no cap
        worst_steps = max(worst_steps, steps)
        if state is not None:
            worst_bits = max(worst_bits, state.bits)
    return worst_steps, worst_bits


def test_every_formula_cell_is_checked() -> None:
    """A ``worst`` or ``at most`` Execution clause has a formula here, and back."""
    stated = {
        row.generator
        for row in load_ledger().rows
        if row.execution_clause.startswith(("worst ", "at most "))
    }
    unchecked = sorted(stated - set(FORMULAS))
    assert not unchecked, f"{unchecked} state a bound with no FORMULAS row; {CHECK}"
    orphaned = sorted(set(FORMULAS) - stated)
    assert not orphaned, f"remove {orphaned} from FORMULAS: no stated bound"
