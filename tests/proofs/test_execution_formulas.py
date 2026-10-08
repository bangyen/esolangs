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
from tests.proofs._ledger import load as load_ledger
from tests.proofs.deep.execution import _dense, run_to_answer
from tests.tools.test_boolean_contract import _parity


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


#: Generator -> (formula in n and the program, exact?, arities).  Mirrors the
#: ledger; ``T`` is 2**n.
FORMULAS: dict[str, tuple[Callable[[int, str], float], bool, tuple[int, ...]]] = {
    "Container": (lambda n, _: 2 * n + 2, True, (3, 7)),
    "Fish": (lambda n, _: 9 * n + 9, True, (3, 6)),
    "Line": (lambda n, _: 5 * n, True, (3, 5)),
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
    "Decleq": (
        lambda n, _: 49 * n + 3 * 2 ** (k := (2 * n - 1).bit_length()) + 2 + n - k,
        False,
        (3, 6),
    ),
    "Qoibl": (lambda n, _: n + 2, True, (3, 6)),
    "RAM0": (lambda n, _: n * n + 8 * n + 5, True, (3, 6)),
    "Algebraic Programming Language": (
        lambda n, _: (65 * n + 1) // 2 - 21,
        True,
        (3, 6),
    ),
    "Alight": (lambda n, _: 2 * n + 5, True, (3, 6)),
    "BF-PDA": (lambda n, _: 10 * n + 2, True, (3, 6)),
    "SStack": (lambda n, _: 7 * n + 3, True, (3, 6)),
    "BrainIf": (lambda n, _: 4 * n + 50, True, (3, 6)),
    "Boolfuck": (lambda n, _: 2 * n * n + 27 * n + 8, True, (3, 6)),
    "Crement": (lambda n, _: 5 * n + 2, True, (3, 6)),
    "Factor": (lambda n, _: 265 * n + 231, True, (4,)),
    "brainfuck": (lambda n, _: 69 * n + 44, True, (3, 6)),
    "Circuit Diagram": (lambda n, _: 2 * n + 1 + (n >= 8), True, (3, 8)),
    "Forbin": (lambda n, _: 2 * max(n - 7, 0) + 2, True, (3, 8)),
    "Inject": (lambda n, _: 8 * n + 10, True, (5, 6)),
    "BFStack": (lambda n, _: 60 * n + 475, True, (8,)),
    # Proved for all n: a path costs at most the all-ones one, and a
    # level's moves at most max(a, b) + 2 over adjacent input cells a, b.
    "Painfuck": (lambda n, _: -(-3 * n * n // 4) + 20 * n + 4, False, (3, 6)),
    "Smallfuck": (lambda n, _: 9 * n * n + 100 * n + 20, False, (3, 6)),
    "Smu": (lambda n, _: 55 * n + 5, True, (3, 6)),
    "Underload": (lambda n, _: 14 * n - 1, False, (3, 6)),
    "FALSE": (lambda n, _: min(12 * n + 69, 10 * n + 99), False, (3, 6)),
    "Jaune": (lambda n, _: 8 * n - 2, False, (3, 6)),
    "Thue": (lambda n, _: 2 * 2**n + 3 * n - 2, True, (3, 6)),
    "Super SNUSP": (lambda n, _: 2 * 2**n + 19 * n + 21, True, (5, 6)),
    "Taglate": (lambda n, _: _taglate(n), True, (3, 4)),
    "thisthat": (
        lambda n, _: (
            32 * 2 ** (n // 2) - 29 if n % 2 == 0 else 48 * 2 ** ((n - 1) // 2) - 29
        ),
        True,
        (3, 4),
    ),
    "3x": (lambda _, p: len(p), True, (3, 5)),
    "Unsquare": (lambda n, _: 2 * 2**n + 79 * n + 26, True, (3, 5)),
    "Vandevelo": (lambda _, p: _vandevelo(p), False, (3, 5)),
    "Home Row": (lambda n, _: 10 * 2**n + 10 * n + 95, True, (3, 5)),
    "Minsky Swap": (lambda n, _: 2 * 2**n + 6 * n + 4, True, (3, 5)),
    "Modulous": (lambda n, _: 5 * 2**n + 5 * n - 2, True, (3, 5)),
    "LaserFuck": (lambda n, _: 18 * 2**n + 56 * n + 5, False, (5,)),
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
    "Minifuck": (lambda _, p: len(p), False, (3, 5)),
    "Dimensional": (lambda n, _: 15 * 2**n - 8 * n + 37, False, (3, 5)),
    "EGL": (lambda n, _: 3 * 2**n + 52 * n + 4, True, (3, 5)),
    "Eval": (lambda n, _: 2 * 2**n + 13 * n + 1, True, (3, 5)),
    "Grapheme": (lambda n, _: 14 * n + 32 + len(str(2**2**n)), True, (3, 5)),
    "Flowchart": (lambda n, _: 3 * 2**n + 9 * n + 4, False, (3, 5)),
    "FRACTRAN": (lambda n, _: n + 2, True, (3, 5)),
    "Suffolk": (lambda _, p: len(p) + 151, True, (3, 5)),
    "Piet": (lambda n, _: 2 * 2**n + 4 * n + 14, True, (3, 5)),
    "Piet++": (lambda n, _: 2 * 2**n + 4 * n + 14, True, (3, 5)),
    "Packlang": (
        lambda n, _: 19 * 2**n // 2 - n - 4 if n <= 7 else 3 * 2**n // 64 + 1206 - n,
        True,
        (3, 7),
    ),
    "S*bleq": (lambda n, _: 3 * n + 2, True, (3, 6)),
    "Sophie": (lambda n, _: 5 * n + 2**n // 4 + 1, False, (3, 5)),
    "Cyclic tag": (lambda n, _: 2 * 2**n + n + 1, True, (3, 5)),
    "///": (lambda n, _: 6 * 2**n + n + 19, True, (3, 5)),
    "Subleq": (
        lambda n, _: 8 * 2**n + (7 * n + 5) * (2**n // n - 1) + 23 * n - 8,
        True,
        (3, 5),
    ),
    "Clockwise": (lambda n, _: 10 * 2**n + 20 * n + 30, True, (3, 5)),
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
    "Back": (lambda n, _: max(2**n, 6 * n - 1) + 2**n + 3 * n + 6, True, (3, 5)),
    "Bitwise Cyclic Tag": (lambda n, _: 5 * 2**n + n, True, (3, 5)),
    "BIO": (lambda n, _: 18 * 2**n - 10 * n + 30, False, (3, 5)),
    "bit~": (lambda n, _: 7 * 2**n + 17 * n + 92, True, (3, 5)),
    "Bitdeque": (lambda n, _: 3 * 2**n + 9 * n - 3, True, (5, 6)),
    "ArrowQueue": (lambda n, _: 11 * 2**n + 6 * n + 24, True, (5, 7)),
    "B-tapemark": (lambda n, _: 4 * 2**n + 42 * n + 5, True, (3, 6)),
    "123": (lambda n, _: 32 * 2**n + 45 * n - 30, True, (4, 6)),
    "6-5": (lambda _, p: len(p), True, (3, 7)),
    "ROTfuck": (lambda n, _: 8 * 4**n + 43 * 2**n + 15 * n - 5, True, (3, 5)),
    "Fargo": (
        lambda n, _: 5 * 2**n + 1 if n > 5 else 15 * 2**n // 2 - 4,
        False,
        (3, 7),
    ),
    "Forþ": (lambda n, _: 6 * 2**n + 12 * n - 3, False, (3, 7)),
    "Unlambda": (lambda n, _: max(77 * n + 12, 84 * n - 9), False, (3, 7)),
    "Streetcode": (
        lambda n, _: 3 * 2**n + 110 * n + 56 if n < 8 else 4 * 2**n + 14 * n + 600,
        True,
        (6, 8),
    ),
}


def _seeded(n: int, seed: int) -> str:
    """A seeded random table; seeds 1 and 3 reach Boolfuck's and BF-PDA's worst."""
    width = 1 << n
    return f"{random.Random(7919 * seed + n).getrandbits(width):0{width}b}"


#: BFStack's worst 7-input block, a rule: 64 zeros, 60 ones, a zero, then ones.
#: Wider, it sits under all-ones top inputs: repeated, it would make them
#: ignored, and they are read and dropped rather than branched.
_BFSTACK_BLOCK = "0" * 64 + "1" * 60 + "0" + "111"


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
        tables += ("0" * (width - 128) + _BFSTACK_BLOCK,)
    if name == "Bitdeque":
        tables += ("10" + "01" * (width // 2 - 1),)
    if name == "123" and n >= 4:
        tables += (_one_two_three_worst(n),)
    if name == "Packlang":
        # The most zeros a 128-row fill block may punch, in every block;
        # zeros are isolated, since a run of ones would be a shorter loop.
        block = min(width, 128)
        zeros = (block - 4) // 2
        tail = block - 2 * (zeros - 1)
        # The odd tail zero keeps every input essential.
        head = "10" * (zeros - 1) + "11" + "0" + "1" * (tail - 3)
        tables += (head * (width // block),)
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
        bits = [(row >> (n - 1 - i)) & 1 for i in range(n)]
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
    assert stated == set(FORMULAS)
