"""Worst-case witness builders: the catalogue's second half.

:mod:`tests.proofs._witnesses` re-exports every name here and keeps
the registries (``_WITNESSES``, ``_SPARSE_ROWS``) that name them; the
builders live apart so that file stays under the size cap.  Each
builder keeps the ``language-owners`` marker the removal tooling
cuts on, exactly as in the parent module.
"""

import importlib
from itertools import islice


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
    """The b = 7 build's worst: 2^(n-7) distinct nonconstant 128-entry blocks.

    Block j is j + 1 in binary; the race reaches it only at n = 12, 13.

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
def _bfstack_block(i: int, e: int) -> str:
    """2^e rows of zeros but one: the worst block, distinct by its row.

    The cascade lists every other row and ends at the last; the one sits at row
    ``1 + i``, never row 0 or the last, whose symmetric tables take the count.
    """
    rows = 2**e
    at = 1 + i if e == 7 else 1
    return "0" * at + "1" + "0" * (rows - at - 1)


def _bfs_chars(n: int) -> str:
    """Distinct worst blocks of up to 128 rows under a tree of blocks."""
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
    """Back's comb-worst tables: Rudin-Shapiro, and from n = 7 the slot witness."""
    width = 1 << n
    # Rudin-Shapiro (parity of 11 pairs in the row), complemented at odd n
    # and with row 1 flipped: the most rows its one-edges cannot share.
    tables = (
        "".join(
            str(bin(i & i >> 1).count("1") % 2 ^ n % 2 ^ (i == 1)) for i in range(width)
        ),
    )
    if n >= 7:
        tables += (
            importlib.import_module("esolangs.languages.back.tests.formulas").witness(
                n
            ),
        )
    return tables
