"""Worst-case witness tables for the execution/workspace formula tests.

``_WITNESSES`` maps a generator to the named tables its exact cells need;
``test_execution_formulas._tables`` appends them to the generic corpus.
``_SPARSE_ROWS`` maps a generator to the named rows of one witness table
that ``test_sparse_rows`` steps where the all-row suites cannot afford to,
and ``_SPARSE_BAND`` carries those cases' duration bands.
"""

import importlib
import random
from collections.abc import Callable
from typing import NamedTuple

import pytest

from esolangs.generation.helpers import reflected_table
from esolangs.runtime._digits import digit_limit_for
from tests.proofs._witness_builders import (
    _back_worst,
    _befunge_worst,
    _bfs_chars,
    _brainif_worst,
    _codesick_chars_worst,
    _collatz_chars_worst,
    _forbin_worst,
    _malbolge_stub,  # noqa: F401 -- re-exported for the formula suites
    _minifuck_worst,
    _row_one,
    _sbleq_worst,
    _smu_worst,
    _suffolk_deep,
    _suffolk_worst,
    _switchcase_worst,
)
from tests.support.witness_tables import parity as _parity


def _seeded(n: int, seed: int) -> str:
    """A deterministic random table for the formula corpus."""
    width = 1 << n
    return f"{random.Random(7919 * seed + n).getrandbits(width):0{width}b}"


def _dig_indexed_worst(n: int) -> str:
    """Distinct six-input leaves, at most ten: the indexed decoder's walk grows
    24 commands per class (``proof_formulas._INDEXED``)."""
    blocks = [_seeded(6, k + 1) for k in range(min(10, 1 << n - 6))]
    return "".join(blocks[i % len(blocks)] for i in range(1 << n - 6))


# language-owners: ["AddSubJump", "Subleq"]
def _asj_packed_worst(n: int) -> str:
    """Top three bits of every chunk set (all chunks widest), the rest hashed.

    Knuth's multiplicative hash on the row index: a dense tree longer than
    the packed decoder, so the decoder ships at its widest.
    """
    width = 1 << n
    rows = []
    for row in range(width):
        chunk, bit = divmod(row, n)
        span = min(n, width - chunk * n)
        rows.append("1" if bit >= span - 3 else str((row * 2654435761 >> 10) & 1))
    return "".join(rows)


# language-owners: ["Subleq"]
def _subleq_packed_worst(n: int) -> str:
    """``_asj_packed_worst`` with the top k bits of each chunk set, k >= 3.

    k is the least that keeps every chunk's value at the digit count of 2^n - 1:
    at n = 10 three bits leave 896..1022, one digit short of 1023 (k = 6).
    """
    digits = len(str((1 << n) - 1))
    k = next(
        (k for k in range(3, n + 1) if ((1 << k) - 1) << (n - k) >= 10 ** (digits - 1)),
        n,
    )
    width = 1 << n
    rows = []
    for row in range(width):
        chunk, bit = divmod(row, n)
        span = min(n, width - chunk * n)
        rows.append("1" if bit >= span - k else str((row * 2654435761 >> 10) & 1))
    return "".join(rows)


# language-owners: ["BFStack"]
#: BFStack's worst 7-input block for execution, a rule: ones at rows 1 and 127.
#: Its 126 zero rows end at 127 and the last row's input is all ones.
_BFSTACK_BLOCK = "0" + "1" + "0" * 125 + "1"


def _bfstack_worst(n: int) -> str:
    """Worst past n = 7, a rule: the block under one arms at every wide level.

    A one arm costs 60 commands a level against a zero arm's 59, and a
    constant zero half keeps every level from folding as equal halves.
    """
    table = _BFSTACK_BLOCK
    while len(table) < 1 << n:
        table = "1" * len(table) + table
    return table


def _bfstack_ws_worst(n: int) -> str:
    """Workspace worst from n = 9, a rule: the deepest block under one arms.

    Every loop opens past half of ``L`` and the stack keeps a sentinel per
    one arm.  The root's zero arm is the one-minterm block ``A`` as the upper
    half at every level, under constant lower halves (alternating); its one
    arm is ``2^(n-8)`` distinct blocks, sized to put the root loop past
    2^(bl(L)-1) with L under 2^bl(L): a single zero among ones, the
    cheapest; at n = 9 a single one, the dearest, which still leaves the
    root loop at 2016 < 2048 (see ``workspace``).
    """
    table = "0" * 64 + "1" + "0" * 63
    for level in range(7, n - 1):
        table = ("1" if level % 2 else "0") * len(table) + table
    for j in range(1 << (n - 8)):
        at = 2 + j
        block = "0" * at + "1" + "0" * (127 - at)
        table += block if n == 9 else "".join("1" if c == "0" else "0" for c in block)
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


# language-owners: ["Boolfuck"]
def _boolfuck_flip(n: int) -> str:
    """Parity with row 5 flipped: not affine, not symmetric, 12 under the tree max."""
    table = _parity(n)
    return table[:5] + str(1 - int(table[5])) + table[6:]


# language-owners: ["Collatz Multiverse"]
def _collatz_worst(n: int) -> str:
    """Cells: the codes' values in order, lowest nonzero last and repeated."""
    m = min(16, 1 << (n - 2))
    kept = sorted(range(16), key=lambda v: (v.bit_count(), v))[16 - m :]
    top = min(v for v in kept if v)
    values = [*(v for v in sorted(kept) if v != top), top]
    cells = [*values, *[top] * ((1 << (n - 2)) - m)]
    return "".join(f"{v & 1}{v >> 1 & 1}{v >> 2 & 1}{v >> 3}" for v in cells)


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
    with digit_limit_for(t):  # 0.31T digits, past the 4300 default from n = 14
        d = len(str(span))
        top = f"{10 ** (d - 1) - 1:0{t}b}"
    covered = []
    for j in range(d):
        lo = 10**j % span
        hi = lo + 10**j
        covered += [(lo, hi)] if hi <= span else [(lo, span), (0, hi - span)]
    v = 10**d % span - 1
    while (hit := next((lo for lo, hi in covered if lo <= v < hi), None)) is not None:
        v = hit - 1 if hit else span - 1
    return top, f"{v:0{t}b}"


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


# language-owners: ["Quassaunt"]
def _quassaunt_stack(n: int) -> str:
    """Equal halves, each ending in 0110: a chain's local, then the heaviest ``If``."""
    half = "0" * ((1 << n - 1) - 4) + "0110"
    return half + half


# language-owners: ["LaserFuck"]
def _laserfuck_worst(n: int) -> tuple[str, ...]:
    """The tree's: nodes all distinct, the all-ones row ending on a one.

    Past n = 6 the lookup's: T - 1 ones in steps, one-hot in bits.
    """
    width = 1 << n
    if n < 7:
        # Also the area's: parity ending on a one at row 0, every node distinct.
        return (
            "".join(str((row.bit_count() + n + 1) & 1) for row in range(width)),
            "".join(str(1 - row.bit_count() % 2) for row in range(width)),
        )
    return "0" + "1" * (width - 1), "1" + "0" * (width - 1)


# language-owners: ["Object disoriented"]
def _od_worst(n: int) -> str:
    """Most distinct subtables per level, the slots left at the knee on constants.

    Level d holds min(2^d, 2^(2^(n-d)) - 2) distinct nodes: a full tree down
    to the knee, whose nodes pair the next level's functions (the first two
    pairs of constants where four slots are spare, else one constant each
    when two are), then every function.
    """
    nodes: list[dict[int, tuple[int, int]]] = [{}] * n
    below: list[int] = []
    fresh = 2
    for d in range(n - 1, -1, -1):
        width = min(2**d, 2 ** (2 ** (n - d)) - 2)
        if d == n - 1:
            pairs = [(0, 1), (1, 0)]
        elif width == 2 ** (2 ** (n - d)) - 2:
            both = [0, 1, *below]
            pairs = [(a, b) for a in both for b in both if not a == b < 2]
        elif len(below) == 2 * width:
            pairs = list(zip(below[::2], below[1::2], strict=True))
        elif 2 * width - len(below) == 2:
            line = [0, below[0], below[1], 1, *below[2:]]
            pairs = list(zip(line[::2], line[1::2], strict=True))
        else:
            size = len(below)
            pairs = [(0, 1), (1, 0)]
            pairs += [
                (below[j], below[(j + t) % size])
                for t in range(1, size)
                for j in range(size)
            ]
            pairs += [p for x in below for c in (0, 1) for p in ((c, x), (x, c))]
            pairs = pairs[:width]
        below = list(range(fresh, fresh + width))
        fresh += width
        nodes[d] = dict(zip(below, pairs, strict=True))
    row = below
    for d in range(n):
        row = [c for x in row for c in (nodes[d][x] if x > 1 else (x, x))]
    return "".join(map(str, row))


# language-owners: ["thisthat"]
def _thisthat_worst(n: int) -> str:
    """Input pairs 01 or 10 by a bit of Knuth's hash: a full tree, nothing shared."""
    return "".join(
        "01" if k * 2654435761 >> 16 & 1 else "10" for k in range(1 << n - 1)
    )


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
    """Every size-s table once, the path nodes last: late indices at every level.

    Tables are ordered by which aligned ``0..01`` blocks of smaller sizes they
    hold (none first), then descending; repeats pair cyclically, first
    occurrences keeping that order.
    """
    s = _first_fit(n, lambda s: (1 << s) - (1 << (s // 2)))
    count, slots = 1 << s, (1 << n) // s

    def key(t: str) -> tuple[list[bool], int]:
        flags = []
        z = s // 2
        while z:
            r = "0" * (z - 1) + "1"
            flags.append(any(t[i : i + z] == r for i in range(0, s, z)))
            z //= 2
        return flags, -int(t, 2)

    order = sorted((f"{k:0{s}b}" for k in range(count)), key=key)
    if slots == count:
        return "".join(order)
    m = count - 1
    out = []
    for k in range(slots // 2 - 1):
        out += [order[k % m], order[(k + 1 + k // m) % m]]
    return "".join(out) + order[0] + order[-1]


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


# language-owners: ["1 + i"]
def _one_i_swapped(m: int) -> str:
    """The largest m-input table: halves swapped, then doubled, from ``0010``."""
    table = "0010"
    while len(table) < 1 << m:
        half = len(table) // 2
        table = table[half:] + table[:half] + table
    return table


def _one_i_worst(n: int) -> str:
    """The all-ones path past maximal zero siblings, a constant at its end."""
    if n <= 13:
        return _one_i_swapped(n)
    if n <= 24:
        return "".join(_one_i_swapped(n - 1 - i) for i in range(4)) + "0" * 2 ** (n - 4)
    return _one_i_swapped(n - 1) + "0" * 2 ** (n - 1)


# language-owners: ["INTERCAL"]
#: Distinct-halved pairs of 2-bit tables, the x / ~x pairs first.
_IC_PAIRS = [
    ("01", "10"),
    ("10", "01"),
    ("00", "01"),
    ("01", "00"),
    ("11", "01"),
    ("01", "11"),
    ("00", "10"),
    ("10", "00"),
    ("11", "10"),
    ("10", "11"),
    ("00", "11"),
    ("11", "00"),
]
#: The same pairs, those reading ``10`` (named after ``01``, so never shorter) first.
_IC_CHAR_PAIRS = [_IC_PAIRS[i] for i in (0, 1, 6, 7, 8, 9, 2, 3, 4, 5, 10, 11)]
#: Diagram nodes per level of the worst-statement table, n = 3..8; past it a full
#: tree to level n - 5, then two levels of its width, 12 and 2.
_IC_WIDTHS = {
    3: (1, 2, 2),
    4: (1, 2, 3, 2),
    5: (1, 2, 4, 4, 2),
    6: (1, 2, 4, 8, 8, 2),
    7: (1, 2, 4, 8, 10, 10, 2),
    8: (1, 2, 4, 8, 16, 16, 12, 2),
}


def _intercal_diagram(widths: tuple[int, ...], pairs: list[tuple[str, str]]) -> str:
    """The table of a diagram with ``widths`` nodes a level over 12 + 2 bottom ones."""
    n = len(widths)
    return _intercal_levels([a + b for a, b in pairs[: widths[n - 2]]], widths[: n - 2])


def _intercal_levels(level: list[str], widths: tuple[int, ...]) -> str:
    """Join ``level`` upward, ``widths`` nodes a level, top first."""
    for w in reversed(widths):
        k = len(level)
        if w >= k:  # every node twice or more, every pair distinct
            edges = [j for i in range(w) for j in (i % k, (i + 1 + i // k) % k)]
        else:  # up then back (an odd k ends on k - 1 so no pair repeats a node)
            back = (
                range(k - 1, -1, -1) if k % 2 == 0 else [*range(k - 2, -1, -1), k - 1]
            )
            edges = [*range(k), *back][: 2 * w]
        level = [level[edges[2 * i]] + level[edges[2 * i + 1]] for i in range(w)]
    return level[0]


def _intercal_worst(n: int) -> str:
    """Diagram with the most named nodes: full unnamed top, lower nodes read twice."""
    if n >= 13:
        # Widest level 2^(n-5) to n = 21, 2^(n-6) from 22, then every ordered
        # pair of the 256 eight-row tables (240 level n - 3 nodes, 16 doubled).
        wide = min(1 << (n - 5), 65280) if n < 22 else 1 << (n - 6)
        rows = [f"{k:08b}" for k in range(256)]
        top = [min(1 << level, wide) for level in range(n - 4)]
        return _intercal_levels(rows, (*top, min(wide, 65280)))
    w = 1 << max(n - 5, 0)
    widths = _IC_WIDTHS.get(n) or (*(1 << i for i in range(n - 4)), w, w, 12, 2)
    return _intercal_diagram(widths, _IC_PAIRS)


def _intercal_chars_worst(n: int) -> str:
    """Diagram with the most nodes: a full tree to level n - 3, then 12 and 2.

    From n = 11 level n - 3 is every distinct-halved pair of 4-bit tables
    (240); the spare slots above re-read its nodes, thirds on the last ones.
    """
    if n >= 11:
        rows = [f"{u:04b}{v:04b}" for u in range(16) for v in range(16) if u != v]
        reads = [*rows, *(rows[i ^ 1] for i in range(240))]
        slots = 1 << (n - 3)
        reads = reads[:slots]
        if slots <= 720:
            for j in range((slots - 480) // 2):
                reads += [
                    rows[240 - (slots - 480) + j],
                    rows[240 - (slots - 480) // 2 + j],
                ]
        else:
            # Third reads (slots - 480 of them) price at the longest name, so
            # they pair up rows named with the most digits: level n - 3 names
            # ascend in first-occurrence (reads) order from 2n + 13, so those
            # rows are a suffix of rows.  Pairs take strides >= 2 inside the
            # suffix, in both directions, so no parent repeats one of the
            # first reads (stride +-1) or another third-read parent.
            need = (slots - 480) // 2
            threshold = 10 ** (len(str(2 * n + 252)) - 1)
            long_rows = rows[max(0, threshold - (2 * n + 13)) :]
            added: list[tuple[str, str]] = []
            stride = 2
            while len(added) < need and stride < len(long_rows):
                for a in range(len(long_rows) - stride):
                    added.append((long_rows[a], long_rows[a + stride]))
                    if len(added) >= need:
                        break
                    added.append((long_rows[a + stride], long_rows[a]))
                    if len(added) >= need:
                        break
                stride += 1
            if len(added) < need:
                raise ValueError(f"the capped shape ends before n = {n}")
            for first_row, second_row in added:
                reads += [first_row, second_row]
        level = [reads[i] + reads[i + 1] for i in range(0, slots, 2)]
        return _intercal_levels(level, tuple(1 << i for i in range(n - 4)))
    widths = (*(1 << i for i in range(n - 2)), min(1 << (n - 2), 12), 2)
    return _intercal_diagram(widths, _IC_CHAR_PAIRS)


def band_marks(band: str | None, case: str) -> list[pytest.MarkDecorator]:
    """Marks for a band; a weekly case names the ledger cell it alone checks."""
    if band is None:
        return []
    if band == "weekly":
        return [pytest.mark.weekly, pytest.mark.cost_evidence(f"ledger: {case}")]
    return [getattr(pytest.mark, band)]


#: (language, n) whose witness build alone passes the fast band, to its band:
#: Interprogck8's scaling test at 8 runs 0.87 s alone, its steps witness included;
#: Back's n = 15 and 16 builds take 1.8 s and 3.8 s, n = 17 takes 9 s.
#: Bleh's ten n = 21 tables take 9.4 s to generate between them, its
#: n = 22 tables 18.5 s, its n = 23 scaling test 23.8 s.
#: Arities past the last one that adds a proof term run weekly: Bleh 21-23
#: and Quassaunt 20, 21 only re-confirm the n - 4 loss term, ~1 min a run.
#: Stisp's tables at n = 18 take 1.6 s to generate between them.
#: S*bleq's scaling cases at n = 21..25 run 10.1 s at n = 21, doubling
#: per arity (the tree build over the corpus tables dominates; the
#: packed witness alone generates in 2.1-28.7 s over the same range).
#: They run weekly: 19 and 20 already reach the 7-digit chunks per push,
#: and the chunk width is one rule; n = 25 took 221 s on CI.
#: What!?'s scaling case at n = 22 runs 9.7 s alone (its corpus tables
#: past 15 inputs are dominated by the two alternating builds); n = 21
#: stays in the medium band at 4.8 s.
#: A case above a language's first per-push arity only backs a ledger
#: range, so it runs weekly: Back 17, Stisp 20, INTERCAL 18-20, What!? 22.
_WITNESS_BAND = {
    ("Interprogck8", 8): "medium",
    ("Back", 15): "medium",
    ("Back", 16): "medium",
    ("Back", 17): "weekly",
    ("Bleh", 21): "weekly",
    ("Bleh", 22): "weekly",
    ("Bleh", 23): "weekly",
    ("Quassaunt", 20): "weekly",
    ("Quassaunt", 21): "weekly",
    ("Stisp", 20): "weekly",
    ("Stisp", 18): "medium",
    ("INTERCAL", 17): "medium",
    ("INTERCAL", 18): "weekly",
    ("INTERCAL", 19): "weekly",
    ("INTERCAL", 20): "weekly",
    ("S*bleq", 21): "weekly",
    ("S*bleq", 22): "weekly",
    ("S*bleq", 23): "weekly",
    ("S*bleq", 24): "weekly",
    ("S*bleq", 25): "weekly",
    ("What!?", 22): "weekly",
}


class SparseRows(NamedTuple):
    """Named rows of one witness table, stepped by the sparse-row suites.

    ``table`` is the witness table at arity ``n``; ``rows`` every row the
    execution suite steps; ``witness`` the row that must attain the
    formulas named by the registration.  The workspace suite samples the
    witness row alone, or ``ws_witness`` when W peaks on another row.
    """

    table: str
    rows: tuple[int, ...]
    witness: int
    ws_witness: int | None = None


# language-owners: ["What!?"]
def _what_sparse(n: int) -> SparseRows:
    """Alternating answers: row 0 attains E, the last row W (past 15 inputs).

    Row 0 satisfies every change point's test; each block's first row ties
    it, the middle and last rows cost less (measured at n = 16, 17).
    """
    width = 1 << n
    rows = (0, 1 << 15, width // 2, width - 1)
    return SparseRows(
        "10" * (width // 2), tuple(dict.fromkeys(rows)), 0, ws_witness=width - 1
    )


# language-owners: ["Interprogck8"]
def _interprogck8_sparse(n: int) -> SparseRows:
    """The steps witness; the named witness row attains E, the rest stay under.

    n = 11: measured over all 2,048 rows, the maximum 38,022 is row 2034 =
    T - 14 alone (2032, 2033, 2035 reach 38,004).  n = 12: rows 4093-4095
    reach 76,006 (of 4000-4095 measured); the witness is the all-ones row.
    """
    owner = importlib.import_module("esolangs.languages.interprogck8.tests.formulas")
    width = 1 << n
    witness = width - 14 if n == 11 else width - 1
    rows = (0, 1, width // 2 - 1, width - 32, width // 2 - 16, width - 16, witness)
    return SparseRows(owner.steps_witness(n), tuple(dict.fromkeys(rows)), witness)


# language-owners: ["S*bleq"]
def _sbleq_sparse(n: int) -> SparseRows:
    """The packed witness's rows, as many as the band affords.

    A row's price is its chunk scan, and the scan's prices are
    chunk-value-driven, not positional (measured per row in the
    landing notes; a case's steps run at ~0.5M/s on a quiet box,
    degrading to ~0.2M/s under a memory-bound co-tenant — the
    sets are budgeted at the degraded rate, against the slow
    band's 600 s hard stop).
    {0, width/2, last} totals 37M steps at n = 21 and stays; at
    22 the middle row alone costs 44M, so {0, last} (34M) stands;
    at 23 every row past chunk 0 costs 60M or more, so chunk 0's
    last bit joins row 0 (12M together).  From n = 24 the chunks
    are 8-digit decimals and row 0 alone costs 40M steps; every
    second row measured there (57M and up) prices its pair past
    the band, so row 0 stands alone.  The dearer rows are
    recorded in the landing notes, unregistered.
    """
    width = 1 << n
    if n == 21:
        rows = (0, width // 2, width - 1)
    elif n == 22:
        rows = (0, width - 1)
    elif n == 23:
        rows = (0, n - 1)
    else:
        rows = (0,)
    return SparseRows(_sbleq_worst(n), rows, rows[-1])


# language-owners: ["Malbolge"]
def _malbolge_symmetric(n: int) -> SparseRows:
    """One weight-class witness at seventeen: named rows, answers only.

    The table is constant on Hamming-weight classes, with the class
    vector drawn from ``Random(17018)`` (eighteen choices, both
    answers attained).  The named rows -- row 0, every single-bit
    row, the first row of every weight and the last two rows --
    probe every folded input and the stub's, attain every weight and
    both answers.  The evidence is about this one weight-class
    witness only: it supports no scaling or execution claim, nothing
    about non-symmetric seventeen-input tables, and it does not
    soften "seventeen is open" -- below seventeen the suites execute
    every row of every corpus table, here only these named rows run.
    The witness field names the last row; no formula column is
    claimed for Malbolge, so it attains nothing.
    """
    rng = random.Random(17018)
    classes = "".join(rng.choice("01") for _ in range(n + 1))
    table = "".join(classes[row.bit_count()] for row in range(1 << n))
    rows = [0]
    for row in (
        *(1 << j for j in range(n)),
        *((1 << w) - 1 for w in range(n + 1)),
        (1 << n) - 2,
        (1 << n) - 1,
    ):
        if row not in rows:
            rows.append(row)
    return SparseRows(table, tuple(rows), rows[-1])


# language-owners: ["Malbolge"]
def _malbolge_sparse(n: int) -> tuple[SparseRows, ...]:
    """The two seventeen-input witnesses: projection and weight-class.

    The projection witness follows; the weight-class witness is
    :func:`_malbolge_symmetric`.  Both are answers-only.
    """
    return _malbolge_projection(n), _malbolge_symmetric(n)


# language-owners: ["Malbolge"]
def _malbolge_projection(n: int) -> SparseRows:
    """One projection witness at seventeen: 36 named rows, answers only.

    The witness is the sparse pricing's measured table (M7): a seeded
    sixteen-input table (``Random(17017)``; the pricing script drew two
    tables from the seed before it, so those draws are consumed here)
    lifted to seventeen by ignoring the last input, each answer then
    appearing under both values of that input.  The eighteen projected
    rows -- row 0, every single-bit row, the half-width row (already a
    single bit) and the last row -- probe every folded input, attain
    both answers and include the step worst (projected row 16, 5,686
    steps, the formula's pinned worst at sixteen); measured on the
    sixteen build they total 100,484 steps, so the lifted 36 rows
    total 200,968, about 0.9 s of stepping.  The evidence is about
    this one projection witness only: it supports no scaling or
    execution claim, nothing about non-projection seventeen-input
    tables, and it does not soften "seventeen is open" -- below
    seventeen the suites execute every row of every corpus table,
    here only these named rows run.
    """
    rng = random.Random(17017)
    for _ in range((1 << (n - 1)) + (1 << n)):
        rng.choice("01")
    base = "".join(rng.choice("01") for _ in range(1 << (n - 1)))
    table = "".join(bit * 2 for bit in base)
    projected = (0, *(1 << j for j in range(n - 1)), (1 << (n - 1)) - 1)
    rows = tuple(2 * row + bit for row in projected for bit in (0, 1))
    return SparseRows(table, rows, 2 * 16)


#: Sparse-row registrations: a witness builder (returning one witness
#: or a tuple of them), the arities to step, and the formula columns
#: (``"execution"``, ``"workspace"``) whose formulas the witness row
#: must attain.  A registration naming no column checks its rows'
#: answers only — the shape a route with no step bound yet (S*bleq's
#: packed route) plugs into.
_SPARSE_ROWS: dict[
    str,
    tuple[
        Callable[[int], SparseRows | tuple[SparseRows, ...]],
        tuple[int, ...],
        frozenset[str],
    ],
] = {
    "What!?": (_what_sparse, (16, 17), frozenset({"execution", "workspace"})),
    "S*bleq": (_sbleq_sparse, (21, 22, 23, 24, 25, 26), frozenset()),
    "Malbolge": (_malbolge_sparse, (17,), frozenset()),
    "Interprogck8": (_interprogck8_sparse, (11, 12), frozenset({"execution"})),
}

#: Sparse-case bands, from standalone runs: a case pays one parse a row
#: stepped, so its cost is its row count times the parse at that arity,
#: plus the stepping (the sampler roughly doubles a row's stepping).
#: What!? parses in ~0.8 s at n = 16, ~1.8 s at 17; whole cases measure
#: 4.2 s / 3.9 s at 16 (execution / workspace) and 11.5 s / 5.7 s at 17.
#: No case at 22 (77 s / 86 s): it reaches no line or branch 16 and 17
#: miss, and past 15 inputs E and W have no case split for it to check;
#: 17 only backs the ledger range, so it runs weekly.
#: S*bleq parses in well under a
#: second even at n = 26; its cases are priced by stepping alone
#: (12M-40M steps a case, plus 1-31 s of generation): whole cases
#: measure 28-108 s standalone (n = 23 the cheapest, 26 the dearest),
#: and up to ~2.4x that under a memory-bound co-tenant.  Past n = 21
#: they run weekly: each re-checks the one packed route at a wider table.  Malbolge
#: parses in about a millisecond at seventeen (the source is the
#: fixed store); its case is generation plus both witnesses' rows
#: (36 projection rows, 35 weight-class rows, 407,729 steps in all),
#: about 1.9 s standalone.
_SPARSE_BAND = {
    ("What!?", "execution", 16): "medium",
    ("What!?", "execution", 17): "weekly",
    ("What!?", "workspace", 16): "medium",
    ("What!?", "workspace", 17): "weekly",
    ("S*bleq", "execution", 21): "slow",
    ("S*bleq", "execution", 22): "weekly",
    ("S*bleq", "execution", 23): "weekly",
    ("S*bleq", "execution", 24): "weekly",
    ("S*bleq", "execution", 25): "weekly",
    ("S*bleq", "execution", 26): "weekly",
    ("Malbolge", "execution", 17): "medium",
    ("Interprogck8", "execution", 11): "medium",
    ("Interprogck8", "execution", 12): "weekly",
}

#: Worst-case witnesses of exact (``worst``) cells the generic corpus misses.
_WITNESSES: dict[str, Callable[[int], tuple[str, ...]]] = {
    "AddSubJump": lambda n: (_asj_packed_worst(n),) if n >= 6 else (),
    "Dig": lambda n: (_dig_indexed_worst(n),) if 8 <= n <= 12 else (),
    "Back": _back_worst,
    # Row 0 marked and T / 2 rows marked, all inputs essential: the
    # complement of parity, whose walk re-runs every row after the first.
    "Tiangou": lambda n: (
        "".join(str(1 - bin(r).count("1") % 2) for r in range(1 << n)),
    ),
    # One-cell runs at both ends: neither corridor direction shortens it (size);
    # a leading run of two and one zero at the end (workspace).
    "A Painter Ant": lambda n: (
        (
            "0" + "1" * ((1 << n) - 2) + "0",
            "110" + "1" * ((1 << n) - 4) + "0",
        )
        if n >= 3
        else ()
    ),
    # The last input ignored: n - 1 essential inputs can outrun all n.
    "B-tapemark": lambda n: (_parity(n - 1) * 2,) if n >= 3 else (),
    "1 + i": lambda n: (_morse("1000", "0010", n), _one_i_worst(n)) if n >= 2 else (),
    "ArrowQueue": lambda n: (_low_one(n),),
    # Workspace: a negated setter's -1 bit on a program as long as the worst
    # (n = 3: a leading run of three zeros, then alternating; from 5, eight).
    "Home Row": lambda n: (
        ("00010101",) if n == 3 else ("0" * 8 + _parity(n)[8:],) if n >= 5 else ()
    ),
    "Polynomial": lambda n: _diagram_witness("polynomial", n, 10),
    # Workspace: the mirrored scan is chosen for a constant prefix then
    # alternating; its line count must still reach the alternating table's
    # bit length (prefix T/8, and T/4 where T/8 stays forward: n = 4).
    "Ascenic": lambda n: (
        "01" * (1 << n - 1),
        *(
            "0" * p + ("01" * (1 << n))[: (1 << n) - p]
            for p in ((1 << n - 3, 1 << n - 2) if n >= 3 else ())
        ),
    ),
    # An 8-row cluster whose root block hops 15 lines (a 33-character body, held
    # by the slot and the calling frame), under equal-half reads.
    "Interprogck8": lambda n: (
        (
            "01100000" * (1 << n - 3),
            *_diagram_witness("interprogck8", n, 10),
            *_diagram_witness("interprogck8", n, 8, "steps_witness"),
        )
        if n >= 3
        else ()
    ),
    "BrainIf": lambda n: (_brainif_worst(n) if n >= 2 else "11",),
    "BFStack": lambda n: (_bfs_chars(n), *_diagram_witness("bfstack", n, 5)),
    "thisthat": lambda n: (_thisthat_worst(n),) if n >= 3 else (),
    "Object disoriented": lambda n: (_od_worst(n),) if n >= 2 else (),
    # Below five its generic families miss the area worst by a column.
    "LaserFuck": lambda n: _laserfuck_worst(n) if n < 5 else (),
    "Bitdeque": lambda n: (_bitdeque_worst(n), _bitdeque_tokens(n)) if n >= 3 else (),
    # Parity with row 0 flipped: a symmetric count table, one flip short.
    "Boolfuck": lambda n: (
        "1" + _parity(n)[1:],
        *(("0000000010010110",) if n == 4 else ()),
        *((_boolfuck_flip(n),) if n >= 3 else ()),
    ),
    # Half the rows set, so table and complement tie: T/2 + 1 ones under a
    # clear top bit (n even), or T/2 ones under a "10" top digit (n odd).
    "Blindfolded Arithmetic": lambda n: (
        "1" * (2 ** (n - 1) + 1) + "0" * (2 ** (n - 1) - 1),
        "1" * (2 ** (n - 1) - 1) + "0" * 2 ** (n - 1) + "1",
    ),
    # Balanced, row 0 a planted one: the longest prologue, and a mark.
    "bit~": lambda n: ("1" * (2 ** (n - 1) - 1) + "01" + "0" * (2 ** (n - 1) - 1),),
    "Circlefuck": lambda n: (_row_one(n),),
    "Caballo": lambda n: ("0010" + _morse("0110", "1001", n)[4:],) if n >= 2 else (),
    "Codesick": lambda n: (
        (_codesick_worst(n), _codesick_chars_worst(n)) if n >= 2 else ()
    ),
    "Collatz Multiverse": lambda n: (
        (_collatz_worst(n), _collatz_chars_worst(n)) if n >= 3 else ()
    ),
    "Crement": lambda n: (_crement_worst(n),) if n >= 3 else (),
    # A one closing each block of 2^k: n - 2 copy jumps in a row.
    "Decleq": lambda n: (
        "".join("0" * (2**k - 1) + "1" for k in range(n - 1, 0, -1)) + "00",
    ),
    "Dimensional": lambda n: (_dimensional_worst(n),) if n >= 4 else (),
    "Fackward": lambda n: (_morse("1000", "0010", n),) if n >= 2 else (),
    "Minifuck": lambda n: (_minifuck_worst(n),) if n >= 3 else (),
    "Forbin": lambda n: (_forbin_worst(n),),
    # Six random subtables tiled by 4 random top inputs: the diagram wins and
    # stores the full 26 lambdas, the variables' peak.
    "FALSE": lambda n: (_false_tiled(n),) if n >= 9 else (),
    # T - 1 runs: alternating but one equal pair.
    "Flowchart": lambda n: ("10" * (2 ** (n - 1) - 1) + "01",),
    "EGL": lambda n: ("10" + "1" * ((1 << n) - 2),),
    "FRACTRAN": lambda n: (_unequal_first(n),) if n >= 2 else (),
    "Befunge": lambda n: (_befunge_worst(n),),
    "Fish": lambda n: (_low_one(n),),
    "Freestajlo": lambda n: (_freestajlo_worst(n), _low_one(n)),
    "Grapheme": lambda n: _grapheme_worst(n) if n >= 2 else (),
    "Hot": lambda n: (_morse("1000", "1011", n),) if n >= 2 else (),
    "INTERCAL": lambda n: (
        (_intercal_worst(n), *((_intercal_chars_worst(n),) if n <= 19 else ()))
        if 3 <= n <= 25
        else ()
    ),
    # Equal halves under parity: the root skip doubles a 3T/2 - 1 term.
    "Kiss": lambda n: (_parity(n - 1) * 2,) if n >= 2 else (),
    # 1 xor parity, the last input ignored at even n: the longest loop sums.
    "Painfuck": lambda n: (
        "".join(str((1 + (r >> 1 - n % 2).bit_count()) % 2) for r in range(1 << n)),
    ),
    "Pointless": lambda n: (_pointless_worst(n),) if n >= 2 else (),
    "Bleh": lambda n: _diagram_witness("bleh", n, 23),
    "Quassaunt": lambda n: (
        _quassaunt_worst(n),
        *((_quassaunt_stack(n),) if n >= 3 else ()),
        *_diagram_witness("quassaunt", n, 21),
    ),
    "S*bleq": lambda n: (_sbleq_worst(n),) if n >= 11 else (),
    "SendStuff": lambda n: (_sendstuff_worst(n),) if n >= 3 else (),
    "Sonata": lambda n: (_low_one(n),),
    "Stisp": lambda n: (
        (_unequal_first(n), *_diagram_witness("stisp", n, 20)) if n >= 2 else ()
    ),
    # From n = 7 the sweep's worst shares; swapped, it ships one shorter.
    "Suffolk": lambda n: (
        (_suffolk_deep(n),)
        if n >= 13
        else (_suffolk_worst(n), *(("10" + _suffolk_worst(n)[2:],) if n >= 7 else ()))
        if n >= 3
        else ()
    ),
    "SwitchCase": lambda n: (_switchcase_worst(n),),
    "Smu": lambda n: (_smu_worst(n),),
    "Modulous": lambda n: (_row_one(n),),
    "Piet": lambda n: (
        tuple(
            dict.fromkeys(
                tuple(_piet_worst(n, kind) for kind in ("area", "steps", "bits"))
                if n <= 7
                else (_piet_worst(n, "area"),)
            )
        )
        if n >= 2
        else ()
    ),
    # n = 9..14: the hashed table ships the packed decoder at its widest.
    "Subleq": lambda n: (
        *((_subleq_worst(n),) if n >= 3 else ()),
        *((_subleq_packed_worst(n),) if n >= 9 else ()),
    ),
    "Underload": lambda n: (_underload_worst(n),) if n >= 3 else (),
}


def _diagram_witness(
    stem: str, n: int, top: int = 8, name: str = "witness"
) -> tuple[str, ...]:
    """The language's dearest-diagram table (its formulas.py), for n = 3..top."""
    if not 3 <= n <= top:
        return ()
    owner = importlib.import_module(f"esolangs.languages.{stem}.tests.formulas")
    return (getattr(owner, name)(n),)


# language-owners: ["Piet"]
def _piet_worst(n: int, kind: str) -> str:
    """Piet's largest shipped area, step count or written bits: the peak z.

    T - z ones spread (the complement past half zeros): at both ends (every
    input essential) and then mid-weight rows, so neither half is constant and
    nothing but the entry count matters.  At n = 7 area peaks at z = 76,
    steps at 65, bits at 101.
    """
    from esolangs.languages.piet.tests.formulas import bit_zeros, walk_zeros, zeros

    width = 1 << n
    middle = [r for r in range(width) if 2 <= r.bit_count() <= n - 2]
    rest = [r for r in range(1, width - 1) if r not in middle]
    z = {"area": zeros, "steps": walk_zeros, "bits": bit_zeros}[kind](n)
    ones = {0, width - 1, *[*middle, *rest][: width - z - 2]}
    return "".join("1" if r in ones else "0" for r in range(width))


def _streetcode_worst(n: int) -> str:
    """Streetcode's largest shipped area and steps: the flat street's longest fill.

    From five inputs, T/2 + 1 ones (the zeros marked, T/2 - 1 of them) is the
    longest fill the flat street writes, and no tree beats it; below, parity.
    """
    if n < 5:
        return _parity(n)
    return "1" + _parity(n)[1:]


def _false_tiled(n: int) -> str:
    """Six random (n - 4)-input subtables, each top-input row one of them."""
    rnd = random.Random(1)
    width = 1 << (n - 4)
    subs = ["".join(rnd.choice("01") for _ in range(width)) for _ in range(6)]
    return "".join(rnd.choice(subs) for _ in range(16))
