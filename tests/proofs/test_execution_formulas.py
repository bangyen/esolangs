"""The Execution column's command formulas hold at small n, over every row.

Each was derived from its generator, not fitted: a fit from parity data
(brainfuck 69n + 41) was beaten by random tables, 458 > 455 at n=6.  An
``exact`` formula must also be reached here; ``bound`` only never exceeded.
"""

import math
import random
from collections.abc import Callable

import esolangs
from esolangs.debugger import make_vm
from esolangs.tools.one_two_three.construction import _leftover
from scripts.benchmark import WrittenState
from tests.generator_support import CHECK
from tests.proofs._formula import ledger_formulas
from tests.proofs._ledger import load as load_ledger
from tests.proofs.deep.execution import _dense, run_to_answer
from tests.witness_tables import parity as _parity
from tests.witness_tables import row_bits


def _taglate(n: int) -> int:
    """Even n past 2, then odd n through a ghost input, m = n + 1."""
    if n % 2 == 0:
        return 16 * 2**n + (7 * n * n + 26 * n - 22) // 2
    m = n + 1
    return 28 * 2**n + (7 * m * m + 22 * m - 36) // 2


def _vandevelo(p: str) -> int:
    """Each ``?`` read, three per comparison, less each guard's final ``loop?``."""
    guards = sum(
        "::" in line and line.rstrip().endswith("loop?") for line in p.splitlines()
    )
    return p.count("?") - guards + 3 * (p.count("==") + p.count("!="))


#: Formulas the ledger notation cannot state: a case split, a definition,
#: a count taken from the program.
_HAND: dict[str, tuple[Callable[[int, str], float], bool, tuple[int, ...]]] = {
    "Container": (lambda n, _: 2 * n + 2, True, (3, 7)),
    # Two passes of the whitespace-free program, the second proving the repeat.
    "A Painter Ant": (lambda _, p: 2 * len("".join(p.split())), True, (3, 6)),
    # Capped rows: straight-line headers, the same count on every table.
    "Befunge": (
        lambda n, _: (
            5 * n + 16 + 4 * -(-n // 2)
            if n <= 8
            else 5 * n + 29
            if n <= 10
            else 5 * n + 67
        ),
        True,
        (3, 9, 11),
    ),
    "Malbolge": (lambda n, _: 478 * n + 1459, True, (3, 6)),
    "BFStack": (lambda n, _: 73 * n + 371 + 13 * (n % 2), True, (8, 9, 10)),
    # Shared one-edges cap the tree at 3T/4 + 1 rows (n=3,4 exhaustive).
    "Back": (
        lambda n, _: max(3 * 2**n // 4 + 1, 6 * n - 1) + 3 * 2**n // 4 + 1 + 3 * n + 6,
        True,
        (3, 5, 6),
    ),
    "Decleq": (
        lambda n, _: 49 * n + 3 * 2 ** (k := (2 * n - 1).bit_length()) + 2 + n - k,
        False,
        (3, 6),
    ),
    "Factor": (lambda n, _: 265 * n + 231, True, (4,)),
    "Circuit Diagram": (lambda n, _: 2 * n + 1 + (n >= 8), True, (3, 8)),
    "FALSE": (lambda n, _: min(12 * n + 69, 10 * n + 99), False, (3, 6)),
    "Taglate": (lambda n, _: _taglate(n), True, (3, 4)),
    "thisthat": (
        lambda n, _: (
            32 * 2 ** (n // 2) - 29 if n % 2 == 0 else 48 * 2 ** ((n - 1) // 2) - 29
        ),
        True,
        (3, 4),
    ),
    "Vandevelo": (lambda _, p: _vandevelo(p), False, (3, 5)),
    "NoComment": (
        lambda n, _: (
            12 * 2**n + 50 * n + 79
            if n <= 6
            else 3 * 2**n + 3 * 2**n // 32 + 240 * n - 491
        ),
        True,
        (4, 7),
    ),
    "INTERCAL": (
        lambda n, _: (
            2 * n + 3 + sum(min(2**k, 2 ** (2 ** (n - k)) - 2) for k in range(1, n))
        ),
        False,
        (3, 5),
    ),
    "Grapheme": (lambda n, _: 14 * n + 32 + len(str(2**2**n)), True, (3, 5)),
    "FRACTRAN": (lambda n, _: n + 2, True, (3, 5)),
    "Packlang": (
        lambda n, _: 19 * 2**n // 2 - n - 4 if n <= 7 else 3 * 2**n // 64 + 1206 - n,
        True,
        (3, 7),
    ),
    "S*bleq": (lambda n, _: 3 * n + 2, True, (3, 6)),
    "Collatz Multiverse": (lambda n, _: 2**n // 4 + 3 * n + 130, False, (3, 6)),
    "CV(N)(C)": (
        lambda n, p: 17 + 4 * n + (n - 1) * (3 + math.sqrt(2 * len(p))),
        False,
        (3, 5),
    ),
    "Circlefuck": (
        lambda n, p: (
            (2 * n + 13) * 2**n + 63 * n + 89 + 2 * sum(map(ord, p[1 : n + 1]))
        ),
        True,
        (3, 5),
    ),
    "Dig": (
        lambda n, _: (
            128 + 46 * 2 ** ((n - 6) // 2)
            if n % 2 == 0
            else 128 + 64 * 2 ** ((n - 7) // 2)
        ),
        True,
        (7,),
    ),
    "AddSubJump": (
        lambda n, _: (11 * n + 4) * (2**n // n) + 11 * 2**n + 13 * n - 17 + (n >= 10),
        True,
        (6,),
    ),
    "ROTfuck": (lambda n, _: 8 * 4**n + 43 * 2**n + 15 * n - 5, True, (3, 5)),
    "Fargo": (
        lambda n, _: 5 * 2**n + 1 if n > 5 else 15 * 2**n // 2 - 4,
        False,
        (3, 7),
    ),
    "Streetcode": (
        lambda n, _: 3 * 2**n + 110 * n + 56 if n < 8 else 4 * 2**n + 14 * n + 600,
        True,
        (6, 8),
    ),
}


#: Arities where the default (see ``ledger_formulas``) is too slow or too
#: shallow for the construction.
_ARITIES: dict[str, tuple[int, ...]] = {
    "Line": (3, 5),
    "Forbin": (3, 8),
    "Inject": (5, 6),
    # Past n = 5: loops of 12 or 14 cells cost 3 a cell (a run of c costs at
    # most 3c); two odd runs keep the last input essential, 2 under 3T each.
    "Unsquare": (6, 7),
    "ArrowQueue": (1, 7),
    "Thue": (3, 6),
    "Super SNUSP": (5, 6),
    "LaserFuck": (5,),
    "Bitdeque": (5, 6),
    "B-tapemark": (3, 6),
    "6-5": (3, 7),
    "Forþ": (3, 7),
    "Unlambda": (3, 7),
}

#: Generator -> (formula, exact?, arities): the ledger's own clause where
#: it parses (``tests/proofs/_formula.py``), else ``_HAND``.
FORMULAS = ledger_formulas(lambda row: row.execution_clause, _HAND, _ARITIES)


def _seeded(n: int, seed: int) -> str:
    """A seeded random table; seeds 1 and 3 reach Boolfuck's and BF-PDA's worst."""
    width = 1 << n
    return f"{random.Random(7919 * seed + n).getrandbits(width):0{width}b}"


#: BFStack's worst 7-input block, a rule: 64 zeros, 60 ones, a zero, then ones.
_BFSTACK_BLOCK = "0" * 64 + "1" * 60 + "0" + "111"


def _bfstack_worst(n: int) -> str:
    """BFStack's worst past n = 7, a rule: the block under classifier nodes.

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


def _one_two_three_worst(n: int) -> str:
    """123's worst, a rule: the all-ones row runs every level three times.

    Rows are read bit-reversed.  The all-ones row answers 0, the next one 1
    (the topmost one, so the kill spans 2T), row 0 carries the one shield,
    and every other row takes whichever answer needs no shield of its own.
    """
    width = 1 << n
    start = width - 1 + 3 * n
    top = start + 2 * (width - 2) + 2
    out = []
    for row in range(width):
        q = int(f"{row:0{n}b}"[::-1], 2)
        if q in {width - 1, 0}:
            out.append("0")
        elif q == width - 2:
            out.append("1")
        else:
            pos = start + 2 * q
            tested = top if (top - pos) % 4 == 0 else top - 1
            out.append("0" if _leftover(n, row & 1, tested - pos) else "1")
    return "".join(out)


def _tables(name: str, n: int) -> tuple[str, ...]:
    """Parity, dense, seeded, constants, AND, both alternations, NAND, ends."""
    width = 1 << n
    if name == "Circuit Diagram" and n >= 8:
        # Its worst, the all-ones H-layout; a wide circuit parses in 0.7s.
        return ("1" * width,)
    if name == "Streetcode":
        # Its worst in both columns on all 10 tables checked to n = 7: all ones.
        return ("1" * width,)
    if name == "Malbolge":
        # Straight-line code: all 10 tables tie at every n measured.
        return (_dense(n),)
    if name == "Befunge":
        # Straight-line code over the inputs that matter; parity has all.
        return (_parity(n),)
    if name == "LaserFuck" and n >= 5:
        # Its worsts, all zeros and all ones; a 3T + 1 cell tape is slow.
        return (_parity(n), _dense(n), "0" * width, "1" * width)
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
        "01" * (width // 2),
    )
    if name == "BFStack" and n >= 7:
        tables += (_bfstack_worst(n),)
    if name == "Bitdeque":
        tables += ("10" + "01" * (width // 2 - 1),)
    if name == "123" and n >= 4:
        tables += (_one_two_three_worst(n),)
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
    return tables


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
