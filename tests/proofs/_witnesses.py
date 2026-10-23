"""Worst-case witness tables for the execution/workspace formula tests.

``_WITNESSES`` maps a generator to the named tables its exact cells need;
``test_execution_formulas._tables`` appends them to the generic corpus.
"""

import importlib
import random
from collections.abc import Callable
from itertools import islice

from esolangs.generation.helpers import reflected_table
from esolangs.runtime._digits import digit_limit_for
from tests.support.witness_tables import parity as _parity


def _seeded(n: int, seed: int) -> str:
    """A deterministic random table for the formula corpus."""
    width = 1 << n
    return f"{random.Random(7919 * seed + n).getrandbits(width):0{width}b}"


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


def _bfstack_ws_worst(n: int) -> str:
    """Workspace worst from n = 9, a rule: the deepest block under one arms.

    Every loop opens past half of ``L`` and the stack keeps a sentinel per
    one arm.  The root's zero arm is the 77-zero block ``A`` as the upper
    half at every level, under constant lower halves (alternating, so no
    node classifies); its one arm is ``2^(n-8)`` distinct patterned blocks,
    the first a 32-bit pattern repeated, sized to put the root loop past
    2^(bl(L)-1).
    """
    table = "0" * 77 + "1" * 51
    for level in range(7, n - 1):
        table = ("1" if level % 2 else "0") * len(table) + table
    for j in range(1 << (n - 8)):
        width = 32 if j == 0 else 64
        half = f"{random.Random(104729 * j + 3).getrandbits(width):0{width}b}"
        table += half * (128 // width)
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
        for j in range((slots - 480) // 2):
            reads += [rows[240 - (slots - 480) + j], rows[240 - (slots - 480) // 2 + j]]
        level = [reads[i] + reads[i + 1] for i in range(0, slots, 2)]
        return _intercal_levels(level, tuple(1 << i for i in range(n - 4)))
    widths = (*(1 << i for i in range(n - 2)), min(1 << (n - 2), 12), 2)
    return _intercal_diagram(widths, _IC_CHAR_PAIRS)


# language-owners: ["Malbolge"]
def _malbolge_stub(n: int) -> str:
    """The all-``1`` label, or from n = 3 the all-``n`` one: the longest stub."""
    return "1" * (1 << n) if n < 3 else "10" * (1 << (n - 1))


# language-owners: ["Collatz Multiverse"]
def _collatz_chars_worst(n: int) -> str:
    """Four-row cells holding the most popcount-heavy values, each once, then 1s."""
    cells = 1 << (n - 2)
    if cells <= 16:
        values = sorted(sorted(range(16), key=lambda v: (-v.bit_count(), -v))[:cells])
    else:
        values = [*range(16), *[1] * (cells - 16)]
    return "".join(str(v >> j & 1) for v in values for j in range(4))


# language-owners: ["BrainIf"]
def _brainif_worst(n: int) -> str:
    """Top-down: layer d's c_d pairs cover layer d-1's symbols; expand through them."""
    counts, prev = [], 2
    for d in range(n):
        prev = min(prev * prev, 1 << (n - 1 - d))
        counts.append(prev)
    pairs, a = [], 2
    for d in range(n):
        cover = [(2 * j, (2 * j + 1) % a) for j in range((a + 1) // 2)]
        seen = set(cover)
        listed = list(dict.fromkeys(cover))
        for x in range(a):
            for y in range(a):
                if len(listed) < counts[d] and (x, y) not in seen:
                    seen.add((x, y))
                    listed.append((x, y))
        pairs.append(listed[: counts[d]])
        a = counts[d]
    seq = [0]
    for d in range(n - 1, -1, -1):
        seq = [s for x in seq for s in pairs[d][x]]
    return "".join(map(str, seq))


# language-owners: ["S*bleq"]
def _sbleq_worst(n: int) -> str:
    """Chunks of n bits, each a d-digit decimal, in a fixed pseudo-random order."""
    chunks, rest = divmod(1 << n, n)
    low = 10 ** (len(str((1 << n) - 1)) - 1)
    span = (1 << n) - low
    bits = [f"{low + (j * 0x9E3779B1) % span:0{n}b}"[::-1] for j in range(chunks)]
    return "".join(bits) + "1" * rest


# language-owners: ["Forbin"]
def _forbin_worst(n: int) -> str:
    """2^(n-7) distinct nonconstant 128-entry blocks (block j is j + 1 in binary).

    Below n = 7 the one-hot table: the whole table is one nonconstant block.
    """
    if n < 7:
        return "0" * ((1 << n) - 1) + "1"
    return "".join(format(j + 1, "0128b") for j in range(1 << (n - 7)))


# language-owners: ["Suffolk"]
def _suffolk_worst(n: int) -> str:
    """Alternating first half, a second half with one equal adjacent pair."""
    h = 1 << (n - 1)
    seq = [1]
    for i in range(1, h):
        seq.append(seq[-1] if i == 1 else 1 - seq[-1])
    return "01" * (h // 2) + "".join(map(str, seq[::-1]))


# language-owners: ["Suffolk"]
def _suffolk_deep(n: int) -> str:
    """From n = 13 the DAG takes one- and two-skip tables: skip three rounds.

    Two skipped sweep rounds in the first half, one in the second, at
    different offsets, so the mixed blocks stay distinct (3n - 5 nodes).
    """
    m = 1 << (n - 1)

    def half(skips: tuple[int, ...]) -> str:
        return "".join(
            str((r + 1 - sum(s <= r for s in skips)) & 1) for r in range(m - 1, -1, -1)
        )

    return half((m // 4 + 1, 3 * m // 4 + 4)) + half((m // 2 + 7,))


# language-owners: ["BFStack"]
#: Marker pair positions in the 128-row block: one pair per quarter.
_BFSTACK_MARKS = (13, 14, 29, 30, 45, 46, 61, 62)


def _bfstack_block(i: int, e: int) -> str:
    """2^e rows, half zeros, last row 0 (pairs 01/10 by the bits of i).

    At e = 7 the four quarters differ by marker pairs.
    """
    pairs = 2 ** (e - 1)
    if e < 7:
        return "".join(
            ("10" if (i >> j) & 1 else "01") if j < pairs - 1 else "10"
            for j in range(pairs)
        )
    free = [j for j in range(63) if j not in _BFSTACK_MARKS]
    bits = ["0"] * 64
    for k, j in enumerate(free):
        bits[j] = str((i >> k) & 1)
    for q in range(4):  # marker pairs 00, 01, 10, 11, one per quarter
        bits[_BFSTACK_MARKS[2 * q]] = str(q >> 1)
        bits[_BFSTACK_MARKS[2 * q + 1]] = str(q & 1)
    bits[63] = "1"
    return "".join("10" if b == "1" else "01" for b in bits)


def _bfs_chars(n: int) -> str:
    """Distinct maximal blocks of up to 128 rows under a tree of blocks."""
    e = min(n, 7)
    return "".join(_bfstack_block(i, e) for i in range(2 ** (n - e)))


# language-owners: ["Smu"]
def _smu_worst(n: int) -> str:
    """Every level filled to capacity: unequal subtables first, then equal ones."""
    if n == 1:
        return "01"

    def size(d: int) -> int:
        return 1 << (n - d)

    def unequal(d: int) -> int:
        return (1 << size(d)) - (1 << (size(d) // 2))

    ds = next(d for d in range(n) if unequal(d) <= 1 << d)
    s = size(ds)
    count = 1 << s
    rows = [f"{k:0{s}b}" for k in range(count)]
    rows = [y for y in rows if y[: s // 2] != y[s // 2 :]] + [
        y for y in rows if y[: s // 2] == y[s // 2 :]
    ]
    if (1 << ds) <= count:
        return "".join(rows[: 1 << ds])
    out = []
    for i in range(1 << (ds - 1)):
        out += [rows[i % count], rows[(i + 1 + i // count) % count]]
    return "".join(out)


# language-owners: ["Codesick"]
def _codesick_chars_worst(n: int) -> str:
    """Saturated quasi-reduced diagram, heaviest id digits at the transition."""
    zero, one = -2, -1  # constants; non-negative values are ranks within a level
    nodes = [min(1 << d, (1 << (1 << (n - d))) - 2) for d in range(n)]
    first = next(d for d in range(n) if (1 << (1 << (n - d))) - 2 <= 1 << d)
    start, low_id = [0] * (n + 1), 2
    for d in range(n - 1, -1, -1):
        start[d] = low_id
        low_id += nodes[d]
    kids: list[list[tuple[int, int]]] = []
    for d in range(n):
        if d < first - 1:  # each child is fresh
            kids.append([(2 * p, 2 * p + 1) for p in range(nodes[d])])
        elif d >= first:  # every pair over the level below, by largest rank
            alphabet = [zero, one, *range(nodes[d + 1] if d + 1 < n else 0)]
            pairs = [(a, b) for a in alphabet for b in alphabet if not (a == b < 0)]
            kids.append(sorted(pairs, key=lambda p: (max(p), p)))
        else:  # transition level: cover low ids, then high ids, then heaviest pairs

            def width(r: int) -> int:
                return len(str(start[first] + r))

            ranks = range(nodes[first])
            # Three id widths: cover every rank once, spares in top-width pairs.
            if width(ranks[-1]) - width(0) > 1:
                top = [r for r in ranks if width(r) == width(ranks[-1])]
                fresh = [(r, r + 1) for r in ranks[::2]]
                spare = (
                    (a, b) for b in top for a in top if not (b == a + 1 and a % 2 == 0)
                )
                kids.append(fresh + list(islice(spare, nodes[d] - len(fresh))))
                continue
            low = [r for r in ranks if width(r) == width(0)]
            high = [r for r in ranks if width(r) > width(0)] or low
            if high is low:
                low = []
            used: list[tuple[int, int]] = []
            seeds = []
            for group in (low, high):
                for i in range(0, len(group), 2):
                    seeds.append(
                        (group[i], group[i + 1] if i + 1 < len(group) else group[0])
                    )
            for pair in seeds:
                if pair not in used and not pair[0] == pair[1] < 0:
                    used.append(pair)
            every = [(a, b) for a in ranks for b in ranks]
            every += [(a, c) for a in ranks for c in (zero, one)]
            every += [(c, a) for a in ranks for c in (zero, one)]
            every += [(zero, one), (one, zero)]

            def weight(x: int) -> int:
                return width(x) if x >= 0 else 1

            every.sort(key=lambda p: -(weight(p[0]) + weight(p[1])))
            for pair in every:
                if len(used) == nodes[d]:
                    break
                if pair not in used and not pair[0] == pair[1] < 0:
                    used.append(pair)
            kids.append(used)
    row = [0]
    for d in range(n):
        row = [x for r in row for x in ((r, r) if r < 0 else kids[d][r])]
    bits = "".join("1" if x == one else "0" for x in row)
    return "".join(bits[int(f"{r:0{n}b}"[::-1], 2)] for r in range(1 << n))


# language-owners: ["Befunge"]
def _befunge_worst(n: int) -> str:
    """Parity of the top k inputs; k = 10 at n = 11, 12.

    There an ignored input beats packing.
    """
    k = 10 if n in (11, 12) else n
    return "".join(str((i >> (n - k)).bit_count() & 1) for i in range(1 << n))


# language-owners: ["SwitchCase"]
def _switchcase_worst(n: int) -> str:
    """A lone one at row T - 2, or T - 3 where row 510 would be an arm of k = 10."""
    t = 1 << n
    row = t - 2 if (t - 2) % 100 != 10 else t - 3
    return "".join("1" if r == row else "0" for r in range(t))


# language-owners: ["Circlefuck", "Modulous"]
def _row_one(n: int) -> str:
    """Row 1 only: every input essential, not symmetric."""
    return "01" + "0" * ((1 << n) - 2)


def _minifuck_worst(n: int) -> str:
    """Controls 1 but the last row's: the strip's writes cost most (4 a one).

    The control is the table bit xor the zero-control row parity, popcount + n.
    """
    return "".join(
        "0" if row == 2**n - 1 else str(1 ^ ((row.bit_count() + n) & 1))
        for row in range(2**n)
    )


def _back_worst(n: int) -> tuple[str, ...]:
    """Back's comb-worst tables: Rudin-Shapiro, and at n = 7-11 a fold-sized one."""
    width = 1 << n
    # Rudin-Shapiro (parity of 11 pairs in the row), complemented at odd n
    # and with row 1 flipped: the most rows its one-edges cannot share.
    tables = (
        "".join(
            str(bin(i & i >> 1).count("1") % 2 ^ n % 2 ^ (i == 1)) for i in range(width)
        ),
    )
    if n in (7, 8):
        # Its fold is smaller (2,280 at n = 7), so the min stops at the fold.
        # This one keeps the comb's rows with few constant pairs, so the fold
        # stays above the comb: the n = 6 seed (60 s anneal, 59 of 64 leaves,
        # 49 rows), doubled with the swapped complement, then at n = 8 with
        # its first entry flipped.
        seed = "1010010110100111010110100100010111011010010110100100101001110101"
        swapped = "".join(seed[i + 1] + seed[i] for i in range(0, 64, 2))
        doubled = seed + "".join("10"[int(c)] for c in swapped)
        if n == 8:
            doubled += str(1 - int(doubled[0])) + doubled[1:]
        tables += (doubled,)
    if n >= 9:
        tables += (
            importlib.import_module("esolangs.languages.back.tests.formulas").witness(
                n
            ),
        )
    return tables


#: (language, n) whose witness build alone passes the fast band, to its band:
#: Interprogck8's steps witness is a 1.3 s recursion at 7 and 9 s at 8.
_WITNESS_BAND = {("Interprogck8", 7): "medium", ("Interprogck8", 8): "slow"}

#: Worst-case witnesses of exact (``worst``) cells the generic corpus misses.
_WITNESSES: dict[str, Callable[[int], tuple[str, ...]]] = {
    "AddSubJump": lambda n: (_asj_packed_worst(n),) if n >= 6 else (),
    "Back": _back_worst,
    # The last input ignored: n - 1 essential inputs can outrun all n.
    "B-tapemark": lambda n: (_parity(n - 1) * 2,) if n >= 3 else (),
    "1 + i": lambda n: (_morse("1000", "0010", n), _one_i_worst(n)) if n >= 2 else (),
    "ArrowQueue": lambda n: (_low_one(n),),
    "Polynomial": lambda n: _diagram_witness("polynomial", n, 10),
    "Ascenic": lambda n: ("01" * (1 << n - 1),),
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
    # All ones but row 0: T - 1 ones and the top octal digit.
    "Blindfolded Arithmetic": lambda n: ("0" + "1" * (2**n - 1),),
    # Balanced, row 0 a planted one: the longest prologue, and a mark.
    "bit~": lambda n: ("1" * (2 ** (n - 1) - 1) + "01" + "0" * (2 ** (n - 1) - 1),),
    "Circlefuck": lambda n: (_row_one(n),),
    "Caballo": lambda n: (_morse("1110", "1011", n),) if n >= 2 else (),
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
        (_intercal_worst(n), *((_intercal_chars_worst(n),) if n <= 12 else ()))
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
    "Bleh": lambda n: _diagram_witness("bleh", n, 18),
    "Quassaunt": lambda n: (
        _quassaunt_worst(n),
        _quassaunt_stack(n),
        *_diagram_witness("quassaunt", n, 12),
    ),
    "S*bleq": lambda n: (_sbleq_worst(n),) if n >= 11 else (),
    "SendStuff": lambda n: (_sendstuff_worst(n),) if n >= 3 else (),
    "Sonata": lambda n: (_low_one(n),),
    "Stisp": lambda n: (
        (_unequal_first(n), *_diagram_witness("stisp", n, 10)) if n >= 2 else ()
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
    "Piet": lambda n: tuple(
        dict.fromkeys(
            tuple(_piet_worst(n, kind) for kind in ("area", "steps", "bits"))
            if n <= 7
            else (_piet_worst(n, "area"),)
        )
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

    T - z ones spread: at both ends (every input essential) and then
    mid-weight rows, so neither half is constant and nothing but the entry
    count matters.  At n = 7 area peaks at z = 126, steps at 113, bits at 108.
    """
    from esolangs.languages.piet.tests.formulas import bit_zeros, walk_zeros, zeros

    width = 1 << n
    middle = [r for r in range(width) if 2 <= r.bit_count() <= n - 2]
    z = {"area": zeros, "steps": walk_zeros, "bits": bit_zeros}[kind](n)
    ones = {0, width - 1, *middle[: width - z - 2]}
    return "".join("1" if r in ones else "0" for r in range(width))


def _streetcode_worst(n: int) -> str:
    """Streetcode's largest shipped area: k zeros on distinct root paths.

    Zero r sits in block bitrev(r) of 2^j (j = bits of k - 1), at offset
    popcount(block) mod 2: the paths split as widely as possible, and no two
    sibling halves are equal, so nothing folds or is drawn once.  k is the
    least count where the tree (4 rows a leaf) is no smaller than the flat street.
    """
    if n < 5:
        return _parity(n)
    gap = sum(max(51, 2 ** (i - 1) + 3) for i in range(1, n))
    k = next(
        k
        for k in range(1, 1 << n)
        if 4 * (8 * n + 20) * (1 + sum(min(1 << d, k) for d in range(n)))
        >= 9 * (2 * (1 << n) - k + 108 + gap)
    )
    bits = (k - 1).bit_length()
    zeros = set()
    for r in range(k):
        block = int(format(r, f"0{bits}b")[::-1], 2) if bits else 0
        zeros.add((block << n - bits) + block.bit_count() % 2)
    return "".join("0" if i in zeros else "1" for i in range(1 << n))


def _false_tiled(n: int) -> str:
    """Six random (n - 4)-input subtables, each top-input row one of them."""
    rnd = random.Random(1)
    width = 1 << (n - 4)
    subs = ["".join(rnd.choice("01") for _ in range(width)) for _ in range(6)]
    return "".join(rnd.choice(subs) for _ in range(16))
