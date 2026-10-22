"""The Execution column's command formulas hold at small n, over every row.

Each was derived from its generator, not fitted: a fit from parity data
(brainfuck 69n + 41) was beaten by random tables, 458 > 455 at n=6.  An
``exact`` formula must also be reached here; ``bound`` only never exceeded.
"""

import random
from collections.abc import Callable

import esolangs
from esolangs.debugger import make_vm
from esolangs.generation.helpers import reflected_table
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


def _morse(a: str, b: str, n: int) -> str:
    """Blocks ``a``, ``b`` in Thue-Morse order: halves both maximal, distinct."""
    for _ in range(n - 2):
        a, b = a + b, b + a
    return a


# language-owners: ["Bitdeque"]
def _bitdeque_worst(n: int) -> str:
    """Every level's zero child an already-placed subtree, read permuted.

    ``Z_k = Z_{k+1} F_{k+1}`` places ``F_{k+1}`` before ``F_k = F_{k+1} W_k``;
    constants of both kinds keep the last level general, and the tree reads
    ``table[r ^ mask]``, odd levels complemented.  Three inputs cannot fit
    both constant kinds: its table is the exhaustive argmax.
    """
    if n == 3:
        return "10110010"
    z, f = "01", "10"
    for k in range(n - 2, 0, -1):
        z, f = z + f, f + str((n - k) % 2) * 2 ** (n - k - 1)
    seen = z + f
    mask = sum(1 << (n - 1 - level) for level in range(1, n, 2))
    return "".join(seen[r ^ mask] for r in range(1 << n))


# language-owners: ["Collatz Multiverse"]
def _collatz_worst(n: int) -> str:
    """Four-row cells holding the base-16 digit sum of their index: 16 differ."""
    return "".join(
        f"{sum(int(d, 16) for d in f'{j:x}') % 16:04b}" for j in range(1 << (n - 2))
    )


# language-owners: ["Dimensional"]
def _dimensional_worst(n: int) -> str:
    """Zero runs of 9 between single ones, one or two of 12 or 15 to fit.

    A counted run of l >= 9 costs 2l + e(l) against 2l, e(l)/(l+1) at most
    2/5 and only at l = 9; the base runs make T + 1 cells reach the knapsack's
    floor((2T+1)/5).
    """
    base = {0: [15], 1: [12], 2: [12] * 5, 3: [12, 15]}[n % 4]
    runs = base + [9] * ((2**n + 1 - sum(r + 1 for r in base)) // 10)
    table = "1".join("0" * r for r in runs)
    return table + "1" * (2**n - len(table))


# language-owners: ["Freestajlo"]
def _freestajlo_worst(n: int) -> str:
    """Sixteen plain entries to n = 6, the others ignored; then 7-bit words."""
    if n <= 2:
        return ("10", "0010")[n - 1]
    if n <= 4:
        return "10" * (2 ** (n - 1) - 1) + "01"
    if n <= 6:
        return "".join(c * 2 ** (n - 4) for c in "10" * 7 + "01")
    return "0110" + "1" * (2**n - 4)


# language-owners: ["Grapheme"]
def _grapheme_worst(n: int) -> tuple[str, ...]:
    """The longest lift, 10^(d-1) - 1, and the largest: the top valid residue."""
    t = 1 << n
    span = 1 << t
    d = len(str(span))
    covered = []
    for j in range(d):
        lo = 10**j % span
        hi = lo + 10**j
        covered += [(lo, hi)] if hi <= span else [(lo, span), (0, hi - span)]
    v = 10**d % span - 1
    while (hit := next((lo for lo, hi in covered if lo <= v < hi), None)) is not None:
        v = hit - 1 if hit else span - 1
    return f"{10 ** (d - 1) - 1:0{t}b}", f"{v:0{t}b}"


# language-owners: ["Quassaunt"]
def _quassaunt_worst(n: int) -> str:
    """Height-k blocks pairing every value, so each level is full or all distinct."""
    k = 0
    while 1 << (k + 1) <= n - k - 1:
        k += 1
    size = 1 << (1 << k)
    blocks = []
    for j in range(1 << (n - k - 1)):
        c, a = divmod(2 * j, size)
        blocks += [a, (a + 1 + c) % size]
    return "".join(f"{v:0{1 << k}b}" for v in blocks)


# language-owners: ["LaserFuck"]
def _laserfuck_worst(n: int) -> tuple[str, ...]:
    """The tree's: nodes all distinct, the all-ones row ending on a one.

    Past n = 6 the lookup's: T - 1 ones in steps, one-hot in bits.
    """
    width = 1 << n
    if n < 7:
        return ("".join(str((row.bit_count() + n + 1) & 1) for row in range(width)),)
    return "0" + "1" * (width - 1), "1" + "0" * (width - 1)


# language-owners: ["Bitdeque"]
def _bitdeque_tokens(n: int) -> str:
    """8-bit blocks (17j + 8) mod 256, distinct pairs from n = 12: most tokens."""
    if n >= 12:
        pairs = ((1 + i % 254, 1 + i // 254 % 254) for i in range(2 ** (n - 4)))
        return "".join(f"{a:08b}{b:08b}" for a, b in pairs)
    offset = 75 if n == 3 else 8
    return "".join(f"{(17 * j + offset) % 256:08b}" for j in range(2 ** (n - 3)))


# language-owners: ["Codesick", "FRACTRAN", "SendStuff", "Stisp"]
def _saturated(n: int, width: int, order: list[str]) -> str:
    """Width-``width`` subtables placed in ``order``, every one if they fit.

    Adjacent entries differ, so every shallower level is distinct too.
    """
    count, slots = len(order), (1 << n) // width
    if slots <= count:
        return "".join(order[:slots])
    return "".join(
        order[i % count] + order[(i + 1 + i // count) % count]
        for i in range(slots // 2)
    )


def _first_fit(n: int, distinct: Callable[[int], int]) -> int:
    """Width of the first depth's subtables whose ``distinct`` count fits."""
    depth = next(d for d in range(n) if distinct(1 << (n - d)) <= 1 << d)
    return 1 << (n - depth)


def _unequal_first(n: int) -> str:
    """Subtables with unequal halves first: the most diagram states."""
    s = _first_fit(n, lambda s: (1 << s) - (1 << (s // 2)))
    rows = [f"{k:0{s}b}" for k in range(1 << s)]
    return _saturated(n, s, sorted(rows, key=lambda y: y[: s // 2] == y[s // 2 :]))


def _codesick_worst(n: int) -> str:
    """Nonconstant subtables first, read bit-reversed: the most nodes."""
    s = _first_fit(n, lambda s: (1 << s) - 2)
    rows = [f"{k:0{s}b}" for k in range(1, (1 << s) - 1)] + ["0" * s, "1" * s]
    table = _saturated(n, s, rows)
    return "".join(table[int(f"{r:0{n}b}"[::-1], 2)] for r in range(1 << n))


def _sendstuff_worst(n: int) -> str:
    """Equal halves last but one pair, unequal ones by last bit: late indices."""
    s = _first_fit(n, lambda s: (1 << s) - (1 << (s // 2)))
    rows = [f"{k:0{s}b}" for k in range(1 << s)]
    same = [y for y in rows if y[: s // 2] == y[s // 2 :]]
    diff = sorted((y for y in rows if y not in same), key=lambda y: (y[-1], y))
    order = [same[-1], same[0], *same[1:-1][::-1], *diff]
    if 1 << n == len(order) * s:
        return "".join([order[1], order[0], *order[2:]])
    count = len(order)
    return "".join(
        order[(i + 1 + i // count) % count] + order[i % count]
        for i in range((1 << n) // s // 2)
    )


# language-owners: ["Crement"]
def _crement_worst(n: int) -> str:
    """Ordered unequal leaf pairs (x, x + d), d from V/2: every level distinct."""
    if n <= 10:
        values = sorted(range(16), key=lambda v: v >> 2 == v & 3)
        cells = []
        for i in range(1 << (n - 3)):
            cells += [values[i % 16], values[(i + 8 + i // 16) % 16]]
        return "".join(f"{v:04b}" for v in cells)
    width = 8 if n <= 19 else 16
    size = 1 << width
    out = []
    for j in range(1 << (n - 4 if width == 8 else n - 5)):
        x, t = j % size, j // size
        d = (t + size // 2 - 1) % (size - 1) + 1
        out += [x, (x + d) % size]
    return "".join(f"{v:0{width}b}" for v in out)


# language-owners: ["Pointless"]
def _pointless_worst(n: int) -> str:
    """Each level's node called twice and the zero leaf thrice: all declared."""
    one, zero = "10", "01"
    for d in range(n - 2, 0, -1):
        one, zero = zero + one, "0" * (1 << (n - d - 1)) + one
    return zero + one


# language-owners: ["Subleq"]
def _subleq_worst(n: int) -> str:
    """Mixed rows, so the packed decoder ships, the last full chunk all ones."""
    chunk = (1 << n) // n - 1
    return "".join(
        "1"
        if r == 0 or chunk * n <= r < chunk * n + n
        else str(bin(r * r).count("1") & 1)
        for r in range(1 << n)
    )


# language-owners: ["Underload"]
def _underload_odd(h: int) -> str:
    """Tree order: the inner table twice at depth 2, so its node carries."""
    if h == 1:
        return "01"
    side = 2 ** (h - 2)
    inner = _underload_odd(h - 2)
    return "0" * side + inner + "1" * side + inner


def _underload_worst(n: int) -> str:
    """A chain of depth-2 carries, one depth-3 for even n, read tested-first."""
    if n % 2:
        tree = _underload_odd(n)
    else:
        zeros, inner = "0" * 2 ** (n - 3), _underload_odd(n - 3)
        tree = 2 * zeros + 2 * inner + 3 * zeros + inner
    return reflected_table(tree, n)


def _low_one(n: int) -> str:
    """One-hot at row T - 2: every input essential, no symmetry."""
    return "0" * ((1 << n) - 2) + "10"


#: Worst-case witnesses of exact (``worst``) cells the generic corpus misses.
_WITNESSES: dict[str, Callable[[int], tuple[str, ...]]] = {
    "1 + i": lambda n: (_morse("1000", "0010", n),) if n >= 2 else (),
    "ArrowQueue": lambda n: (_low_one(n),),
    "Bitdeque": lambda n: (_bitdeque_worst(n), _bitdeque_tokens(n)) if n >= 3 else (),
    # Parity with row 0 flipped: a symmetric count table, one flip short.
    "Boolfuck": lambda n: (
        "1" + _parity(n)[1:],
        *(("0000000010010110",) if n == 4 else ()),
    ),
    # All ones but row 0: T - 1 ones and the top octal digit.
    "Blindfolded Arithmetic": lambda n: ("0" + "1" * (2**n - 1),),
    # Balanced, row 0 a planted one: the longest prologue, and a mark.
    "bit~": lambda n: ("1" * (2 ** (n - 1) - 1) + "01" + "0" * (2 ** (n - 1) - 1),),
    "Caballo": lambda n: (_morse("1110", "1011", n),) if n >= 2 else (),
    "Codesick": lambda n: (_codesick_worst(n),) if n >= 2 else (),
    "Collatz Multiverse": lambda n: (_collatz_worst(n),) if n >= 2 else (),
    "Crement": lambda n: (_crement_worst(n),) if n >= 3 else (),
    # A one closing each block of 2^k: n - 2 copy jumps in a row.
    "Decleq": lambda n: (
        "".join("0" * (2**k - 1) + "1" for k in range(n - 1, 0, -1)) + "00",
    ),
    "Dimensional": lambda n: (_dimensional_worst(n),) if n >= 4 else (),
    "Fackward": lambda n: (_morse("1000", "0010", n),) if n >= 2 else (),
    # T - 1 runs: alternating but one equal pair.
    "Flowchart": lambda n: ("10" * (2 ** (n - 1) - 1) + "01",),
    "FRACTRAN": lambda n: (_unequal_first(n),) if n >= 2 else (),
    "Fish": lambda n: (_low_one(n),),
    "Freestajlo": lambda n: (_freestajlo_worst(n), _low_one(n)),
    "Grapheme": lambda n: _grapheme_worst(n) if n >= 2 else (),
    "Hot": lambda n: (_morse("1000", "1011", n),) if n >= 2 else (),
    # Equal halves under parity: the root skip doubles a 3T/2 - 1 term.
    "Kiss": lambda n: (_parity(n - 1) * 2,) if n >= 2 else (),
    # 1 xor parity, the last input ignored at even n: the longest loop sums.
    "Painfuck": lambda n: (
        "".join(str((1 + (r >> 1 - n % 2).bit_count()) % 2) for r in range(1 << n)),
    ),
    "Pointless": lambda n: (_pointless_worst(n),) if n >= 2 else (),
    "Quassaunt": lambda n: (_quassaunt_worst(n),),
    "SendStuff": lambda n: (_sendstuff_worst(n),) if n >= 3 else (),
    "Stisp": lambda n: (_unequal_first(n),) if n >= 2 else (),
    "Subleq": lambda n: (_subleq_worst(n),) if n >= 3 else (),
    "Underload": lambda n: (_underload_worst(n),) if n >= 3 else (),
}


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
        return (_parity(n), _dense(n), "0" * width, "1" * width, *_laserfuck_worst(n))
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
    if name in {"ArrowQueue", "EGL", "Minsky Swap", "ROTfuck"}:
        # Their worst, exhaustive through n=3: a lone zero, second to last.
        # ROTfuck's was NAND's, and Minsky Swap's and EGL's parity, until
        # symmetric tables took the count.
        tables += ("1" * (width - 2) + "01",)
    if name in _WITNESSES:
        tables += _WITNESSES[name](n)
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
