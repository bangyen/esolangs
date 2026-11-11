"""Shared witness builders and scheduling for resource formula tests."""

import random
from collections.abc import Callable
from typing import NamedTuple

import pytest

from esolangs.generation.helpers import permute_truth_table, reflected_table
from esolangs.registry import LANGUAGES
from esolangs.runtime._digits import digit_limit_for
from scripts.docs.fragments import section
from scripts.docs.resource_evidence import PACKAGES, _provider
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
#: BFStack's worst 8-input block for execution, a rule: ones at rows 1 and 255.
#: Its 253 zero rows end at 254 and the last row's input is all ones.
_BFSTACK_BLOCK = "0" + "1" + "0" * 253 + "1"


def _bfstack_worst(n: int) -> str:
    """Worst from n = 8, a rule: the block under one arms at every wide level.

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
    arm is ``2^(n-9)`` distinct blocks, sized to put the root loop past
    2^(bl(L)-1) with L under 2^bl(L): a single zero among ones, the
    cheapest; at n = 9 a single one, the dearest, which still leaves the
    root loop below 2048 (see ``workspace``).
    """
    table = "0" * 128 + "1" + "0" * 127
    for level in range(8, n - 1):
        table = ("1" if level % 2 else "0") * len(table) + table
    for j in range(1 << (n - 9)):
        at = 2 + j
        block = "0" * at + "1" + "0" * (255 - at)
        table += block if n == 9 else "".join("1" if c == "0" else "0" for c in block)
    return table


def _morse(a: str, b: str, n: int) -> str:
    """Blocks ``a``, ``b`` in Thue-Morse order: halves both maximal, distinct."""
    for _ in range(n - 2):
        a, b = a + b, b + a
    return a


# language-owners: ["Caballo"]
def _caballo_chain(n: int) -> str:
    """The execution worst: every zero child holds a lone-1 dp chain.

    Row 0...0 skips one chain per level, 2 items a level; the tree is built
    on the complement, which has the fewer ones.
    """
    tree, size = "10", 2
    while size < 2**n:
        tree += "0" * (size - 1) + "1"
        size *= 2
    return "".join("10"[c == "1"] for c in tree) if n > 2 else tree


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

    Past six, retain old extremes; last-onehot attains the new tape peak.
    """
    width = 1 << n
    if n < 7:
        # Also the area's: parity ending on a one at row 0, every node distinct.
        return (
            "".join(str((row.bit_count() + n + 1) & 1) for row in range(width)),
            "".join(str(1 - row.bit_count() % 2) for row in range(width)),
        )
    return (
        "0" + "1" * (width - 1),
        "1" + "0" * (width - 1),
        "0" * (width - 1) + "1",
    )


# language-owners: ["Object disoriented"]
def _od_worst(n: int) -> str:
    """Realize the proof's width profile, pairing spare slots with constants.

    Cheaper nodes change the extremal widths: reconstruct the profile from
    the independent count proof instead of retaining a stale maximal-width
    fixture. This is verification, never a table used by the generator.
    """
    from esolangs.languages.object_disoriented.tests.formulas import _profile

    widths = (
        _profile(n)[1]
        if n <= 8
        else tuple(min(2**d, 2 ** (2 ** (n - d)) - 2) for d in range(n))
    )
    nodes: list[dict[int, tuple[int, int]]] = [{}] * n
    below: list[int] = []
    fresh = 2
    for d in range(n - 1, -1, -1):
        width = widths[d]
        if d == n - 1:
            pairs = [(0, 1), (1, 0)]
        elif width == 2 ** (2 ** (n - d)) - 2:
            both = [0, 1, *below]
            pairs = [(a, b) for a in both for b in both if not a == b < 2]
        elif len(below) == 2 * width:
            pairs = list(zip(below[::2], below[1::2], strict=True))
        elif 2 * width - len(below) == 1:
            line = [1, *below]
            pairs = list(zip(line[::2], line[1::2], strict=True))
        else:
            spare = 2 * width - len(below)
            pairs = [(0, 1)]
            if spare >= 4 and (
                width - 2 >= len(below) or 2 * (width - 2) == len(below)
            ):
                pairs.append((1, 0))
            count = width - len(pairs)
            if 2 * count == len(below):
                pairs += list(zip(below[::2], below[1::2], strict=True))
            else:
                size = len(below)
                pairs += [
                    (below[j], below[(j + t) % size])
                    for t in range(size)
                    for j in range(size)
                ][:count]
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
        else str((r * r).bit_count() & 1)
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


def _eval_alternating_upper(n: int) -> str:
    """Parity below, ``1010..`` above before Gray carrying; every input essential."""
    half = 1 << n - 1
    stacked = _parity(n - 1) + "10" * (half // 2)
    return permute_truth_table(stacked, tuple(reversed(range(n))))


# language-owners: ["1 + i"]
def _one_i_swapped(m: int) -> str:
    """The largest m-input table, the workspace worst: swap halves, double."""
    table = "0010"
    while len(table) < 1 << m:
        half = len(table) // 2
        table = table[half:] + table[:half] + table
    return table


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
#: Historical old-policy width profiles retained for coverage, n = 3..8;
#: then a full tree to level n - 5 and two levels of its width, 12 and 2.
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
    """Historical old-policy naming witness, retained for coverage."""
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


def _intercal_chars_shifted(n: int) -> str:
    """The shifted cap at n >= 20: level n - 4 holds all 65,280 pairs.

    The level n - 4 occurrence sequence runs in rounds over every
    ordered pair of distinct eight-row values: round one lists them
    all (lex order, so the values read extra times come last and take
    the longest names), each later round re-lists the values whose
    read count reaches it under its own stride permutation, whose
    consecutive pairs are new parents, distinct with unequal halves.
    Reads spread r0 = 2^(n-4) // 65,280 per value plus one more on
    the last rem values; above the level the tree is full.
    """
    from math import gcd

    values = [f"{a:08b}{b:08b}" for a in range(256) for b in range(256) if a != b]
    cap = len(values)
    r0, rem = divmod(1 << (n - 4), cap)
    strides = (7, 11, 13, 19, 23, 29, 31, 37)
    rounds = [values]
    for k in range(2, r0 + 2):
        subset = values if k <= r0 else values[cap - rem :]
        stride = strides[k - 2]
        assert gcd(stride, len(subset)) == 1
        rounds.append([subset[(i * stride) % len(subset)] for i in range(len(subset))])
    return "".join(v for rnd in rounds for v in rnd)


def _intercal_chars_plateau(n: int) -> str:
    """The shifted cap under a plateau at level n - 5, from n = 22.

    The capped level's occurrence sequence runs in rounds over every
    value — r0 = 2^(n-5) // 65,280 full rounds (the first in lex
    order, the rest stride-permuted), then one stride round over the
    last rem values — as in the shifted build; its consecutive pairs
    are the plateau's 2^(n-6) distinct nodes, and the level n - 5
    sequence lists those pairs once in order and once
    stride-permuted, so every plateau node is read twice and named.
    At n = 22 this is the original build: rounds at strides 7 and 11
    over a 512-value tail.
    """
    from math import gcd

    values = [f"{a:08b}{b:08b}" for a in range(256) for b in range(256) if a != b]
    cap = len(values)
    x = 1 << (n - 6)
    r0, rem = divmod(2 * x, cap)
    strides = (7, 11, 13, 19, 23, 29, 31, 37)
    rounds = [values]
    for k in range(2, r0 + 1):
        stride = strides[k - 2]
        assert gcd(stride, cap) == 1
        rounds.append([values[(i * stride) % cap] for i in range(cap)])
    if rem:
        tail = values[cap - rem :]
        stride = strides[r0 - 1]
        assert gcd(stride, len(tail)) == 1
        rounds.append([tail[(i * stride) % len(tail)] for i in range(len(tail))])
    seq = [v for rnd in rounds for v in rnd]
    pairs = [(seq[2 * i], seq[2 * i + 1]) for i in range(x)]
    assert gcd(13, x) == 1
    order = [(i * 13) % x for i in range(x)]
    return "".join(a + b for a, b in pairs) + "".join(
        pairs[i][0] + pairs[i][1] for i in order
    )


def _intercal_chars_worst(n: int) -> str:
    """Diagram with the most nodes: a full tree to level n - 3, then 12 and 2.

    From n = 11 level n - 3 is every distinct-halved pair of 4-bit tables
    (240); the spare slots above re-read its nodes, thirds on the last ones.
    From n = 20 the cap shifts to level n - 4 (:func:`_intercal_chars_shifted`),
    from n = 22 under a plateau (:func:`_intercal_chars_plateau`).
    """
    if n >= 22:
        return _intercal_chars_plateau(n)
    if n >= 20:
        return _intercal_chars_shifted(n)
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
#: Bleh's ten n = 18 tables take 1.7 s to generate between them, its
#: ten n = 21 tables 9.4 s, its
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
#: range, so it runs weekly: Back 17, Stisp 20, INTERCAL 18-24, What!? 22.
#: INTERCAL's scaling cases at n = 20..23 run 25 s, 47 s, 90 s and
#: 151 s alone (corpus generations dominate; n = 24 checks the bound).
#: INTERCAL at n = 14 and 15 measured 9.0 s and 10.8 s on CI (weekly
#: runs of 2026-11-02) -- over the 3 s fast band, with the formulas
#: themselves holding in both runs; n = 16 stayed inside the band.
#: Circuit Diagram at n = 11 measured 7.6 s and 8.9 s on CI in two
#: consecutive weekly runs (2026-11-02), again with the formula holding;
#: a repeat overrun at that margin is the band, not a flake.
_WITNESS_BAND = {
    ("Circuit Diagram", 11): "medium",
    ("Interprogck8", 8): "medium",
    ("Back", 15): "medium",
    ("Back", 16): "medium",
    ("Back", 17): "weekly",
    ("Bleh", 18): "medium",
    ("Bleh", 21): "weekly",
    ("Bleh", 22): "weekly",
    ("Bleh", 23): "weekly",
    ("Quassaunt", 20): "weekly",
    ("Quassaunt", 21): "weekly",
    ("Stisp", 20): "weekly",
    ("Stisp", 18): "medium",
    ("INTERCAL", 14): "medium",
    ("INTERCAL", 15): "medium",
    ("INTERCAL", 17): "medium",
    ("INTERCAL", 18): "weekly",
    ("INTERCAL", 19): "weekly",
    ("INTERCAL", 20): "weekly",
    ("INTERCAL", 21): "weekly",
    ("INTERCAL", 22): "weekly",
    ("INTERCAL", 23): "weekly",
    ("INTERCAL", 24): "weekly",
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


class SparseRegistration(NamedTuple):
    """Language-owned sparse witnesses, formula columns and run bands."""

    build: Callable[[int], SparseRows | tuple[SparseRows, ...]]
    arities: tuple[int, ...]
    columns: frozenset[str]
    bands: dict[int, str]


def sparse_registrations() -> dict[str, SparseRegistration]:
    """Load and validate sparse witness declarations for the proof suites."""
    found = {}
    for name, language in LANGUAGES.items():
        path = PACKAGES / language.id / "language.toml"
        row = (section(path, "resource_evidence") or {}).get("sparse")
        if row is None:
            continue
        if not isinstance(row, dict) or set(row) != {
            "provider",
            "arities",
            "columns",
            "bands",
        }:
            raise ValueError(f"{path}: invalid sparse witness declaration")
        arities = row["arities"]
        columns = row["columns"]
        bands = row["bands"]
        if (
            not isinstance(arities, list)
            or not arities
            or any(type(arity) is not int or arity < 1 for arity in arities)
            or len(arities) != len(set(arities))
            or not isinstance(columns, list)
            or any(column not in ("execution", "workspace") for column in columns)
            or not isinstance(bands, dict)
            or set(bands) != {str(arity) for arity in arities}
            or any(band not in ("medium", "slow", "weekly") for band in bands.values())
        ):
            raise ValueError(f"{path}: invalid sparse witness scope")
        found[name] = SparseRegistration(
            _provider(name, row["provider"]),
            tuple(arities),
            frozenset(columns),
            {int(arity): band for arity, band in bands.items()},
        )
    return found
