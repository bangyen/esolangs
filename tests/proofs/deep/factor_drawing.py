"""The enumerative lookup: every drawn character carries log2(1 + sqrt 2) bits.

Run:  just proofs   (or python tests/proofs/deep/factor_drawing.py)

``docs/proofs/factor.tex`` closes the construction side of the leading
constant.  A table is carried as tape data; a program that draws a tape with
``C`` characters of ``><+-`` can reach at most about ``(1 + sqrt 2)**C``
distinct tapes, so ``T`` bits need ``T / log2(1 + sqrt 2) = 0.7864 T``
characters, and an enumerative code reaches that: a group of ``k`` entries is
one integer vector of ``S`` cells with L1 norm at most ``M``, of which there
are ``D(S, M)`` (Delannoy), and ``(S + M) / log2 D(S, M)`` tends to
``1 / log2(1 + sqrt 2)``.  The chain's hop loops are scans over rail cells
rather than runs, so everything but the drawing is ``o(T)``.

L10   the layout: emitted length matches its closed form, and the program
     runs, exhaustively at small arity with a small radix so that every hop
     level, including the rail scans, executes.
L11  the prices: ``(S + M) / k`` at the best ``(S, M)`` for each ``k``, the
     limit ``1 / log2(1 + sqrt 2)``, and the digit constant ``0.3415``.
L12  the floor: a shortest source has none of the five cancelling
     adjacencies, so class words grow like ``lambda = 6.388``, the largest
     root of ``x^3 - 4x^2 - 14x - 8``, and the floor is ``0.1505``.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tests.proofs.deep._delannoy_decoder import (
    ball_rank,
    ball_unrank,
    delannoy,
    rank_decoder,
)

#: Cost band; see ``__main__.py``.
BAND = "by-hand"
COST = 16.0


#: A block above the groups ends in ``[A][A'][z_0]..[z_(L-1)]``: the anchor
#: pair the hop counter lives in, then one rail cell per chain level.  The
#: rail ``z_l`` of a level-``l`` block is 1 unless the block is the last among
#: its siblings; every other rail is 0.  A scan at level ``l`` runs over its
#: sub-blocks' ``z_(l-1)`` cells and stops on the parent's neighbour, whose
#: ``z_(l-1)`` is 0; the scans nested inside it land on that neighbour's
#: lower rails, which are 0 too.  One cell a level is what makes the two
#: requirements compatible.
def trailer(sizes: list[int]) -> int:
    """Cells after a block's sub-blocks: two anchors and a rail a level."""
    return len(sizes) + 2


#: The paper's radix is 256, the largest a byte counter allows; the tests
#: shrink it so that several levels, and so the rail scans, fit at small n.
RADIX_BITS = 8


def layout(chain_bits: int, group: int, radix_bits: int) -> tuple[list[int], list[int]]:
    """``(chunk sizes top-down, block widths bottom-up)``.

    Widths start at the group and end at the whole span.  The short chunk
    goes second from the top, as in the chained lookup.
    """
    if chain_bits == 0:
        return [], [group]
    levels = -(-chain_bits // radix_bits)
    rest = chain_bits - radix_bits * (levels - 1)
    if levels == 1:
        sizes = [chain_bits]
    elif levels == 2:
        sizes = [radix_bits, rest]
    else:
        sizes = [radix_bits, rest] + [radix_bits] * (levels - 2)
    blocks = [group]
    for size in reversed(sizes):
        blocks.append((1 << size) * blocks[-1] + trailer(sizes))
    return sizes, blocks


def group_start(g: int, sizes: list[int], blocks: list[int]) -> int:
    """The walk cell of group ``g``; the layout is reversed at every level."""
    digits, rest = [], g
    for size in reversed(sizes):
        digits.append(rest & ((1 << size) - 1))
        rest >>= size
    digits.reverse()
    top = len(sizes)
    return sum(
        ((1 << size) - 1 - digits[k]) * blocks[top - 1 - k]
        for k, size in enumerate(sizes)
    )


def rails(sizes: list[int], blocks: list[int]) -> dict[int, int]:
    """Cells holding 1: rail ``z_l`` of every level-``l`` block that is not
    the last among its siblings."""
    ones: dict[int, int] = {}
    top, tr = len(sizes), trailer(sizes)

    def fill(level: int, pos: int, *, last: bool) -> None:
        if level == 0:
            return
        width = blocks[level - 1]
        radix = 1 << sizes[top - level]
        for i in range(radix):
            fill(level - 1, pos + i * width, last=i == radix - 1)
        if not last:
            ones[pos + blocks[level] - tr + 2 + level] = 1

    fill(top, 0, last=True)
    assert len(ones) == rail_count(sizes)
    return ones


def rail_count(sizes: list[int]) -> int:
    """How many rails hold 1: at each level, every block but the last of
    each sibling set, which is ``(r - 1) / r`` of the blocks there."""
    total, above = 0, 1
    for size in sizes[:-1]:  # the last size is the groups', which have none
        radix = 1 << size
        total += above * (radix - 1)
        above *= radix
    return total


def scan(level: int, sizes: list[int], blocks: list[int], *, left: bool) -> str:
    """Move by one level-``level`` block, from its rail ``z_level`` to the
    same rail of the neighbouring block.

    Level 1 is a plain run.  Above it the move is a scan over the
    sub-blocks' rails ``z_(level-1)``: leftward it runs on to the parent's
    left neighbour, whose rail is 0; rightward it stops on the last
    sub-block, whose rail is 0.
    """
    if level == 1:
        return ("<" if left else ">") * blocks[1]
    inner = scan(level - 1, sizes, blocks, left=left)
    tr = trailer(sizes)
    if left:
        # z_level(X) is tr + 1 cells right of z_(level-1) of X's last sub-block.
        return "<" * (tr + 1) + inner + "[" + inner + "]" + ">"
    return "<" + inner + "[" + inner + "]" + ">" * (tr + 1)


def hop(level: int, sizes: list[int], blocks: list[int]) -> str:
    """The carried-counter hop over level-``level`` sub-blocks, from an
    anchor; lands on the anchor ``d`` sub-blocks to the left, zeroed."""
    if level == 0:
        step_l, step_r = "<" * blocks[0], ">" * blocks[0]
    else:
        # The anchor A opens the trailer; z_level is 2 + level cells right.
        to_rail, back = ">" * (2 + level), "<" * (2 + level)
        step_l = to_rail + scan(level, sizes, blocks, left=True) + back
        step_r = to_rail + scan(level, sizes, blocks, left=False) + back
    return "[[-" + step_l + "+" + step_r + "]" + step_l + "-]"


def read_chunk(size: int) -> str:
    """Accumulate ``size`` input bits into the anchor as ``a -> 2a + b``."""
    return ("[->++<]>[-<+>]<>," + "-" * 48 + "[-<+>]<") * size


def bf_drawing(
    truth_table: str,
    size: int,
    m: int,
    bits: int,
    radix_bits: int = RADIX_BITS,
    decoder: str | None = None,
) -> str:
    """The enumerative lookup of Lemma "Enumerative lookup"."""
    n = int(math.log2(len(truth_table)))
    assert bits <= n, (bits, n)
    k = 1 << bits
    assert delannoy(size, m) >= 1 << k, (size, m, k)
    sizes, blocks = layout(n - bits, size + 1, radix_bits)
    span, tr = blocks[-1], trailer(sizes)
    cells = dict(rails(sizes, blocks))
    for g in range(len(truth_table) >> bits):
        block = truth_table[g * k : (g + 1) * k]
        value = sum(int(block[j]) << j for j in range(k))
        start = group_start(g, sizes, blocks)
        for i, v in enumerate(ball_unrank(value, size, m)):
            if v:
                cells[start + 1 + i] = v % 256

    out = []
    end = span - tr if sizes else size
    for cell in range(end + 1):
        value = cells.get(cell, 0)
        out.append("+" * value if value < 128 else "-" * (256 - value))
        if cell < end:
            out.append(">")
    if not sizes:
        out.append("<" * size)
    top = len(sizes)
    for kk, chunk in enumerate(sizes):
        level = top - 1 - kk
        out.append(read_chunk(chunk))
        seat = tr if level >= 1 else blocks[0]
        out.append("[-" + "<" * seat + "+" + ">" * seat + "]" + "<" * seat)
        out.append(hop(level, sizes, blocks))
    out.append(decoder if decoder is not None else rank_decoder(size, m, bits))
    return "".join(out)


def drawing_length(
    n: int, size: int, bits: int, marks: int, radix_bits: int, decoder: int
) -> int:
    """Closed form for what :func:`bf_drawing` emits, given the marks."""
    sizes, blocks = layout(n - bits, size + 1, radix_bits)
    tr = trailer(sizes)
    total = (blocks[-1] - tr if sizes else size) + marks + rail_count(sizes)
    if not sizes:
        total += size
    top = len(sizes)
    for kk, chunk in enumerate(sizes):
        level = top - 1 - kk
        seat = tr if level >= 1 else blocks[0]
        total += 72 * chunk + 3 * seat + 4 + len(hop(level, sizes, blocks))
    return total + decoder


def tree_decoder(size: int, m: int, bits: int) -> str:
    """A decision tree over the cells, the reference for small parameters.

    Reads the index bits into interleaved cells right of the data, moves
    each cell's value plus ``m`` next to a flag cell, and switches on it by
    the parked-byte idiom; at the leaf the block is known and a tree on
    the index bits prints its bit.
    """
    base = size + 1  # first free cell after the data, relative to W
    j_cell = [base + 2 * i for i in range(bits)]
    x_cell = [base + 2 * bits + 2 * i for i in range(size)]
    out = []
    for i in range(bits):
        out.append(">" * j_cell[i] + "[-]>[-]<," + "-" * 48 + "<" * j_cell[i])
    for i in range(size):
        delta = x_cell[i] - (1 + i)
        # The x cell and its flag are junk: clear both before the move.
        out.append(">" * x_cell[i] + "[-]>[-]<" + "<" * x_cell[i])
        out.append(
            ">" * (1 + i) + "[-" + ">" * delta + "+" + "<" * delta + "]" + ">" * delta
        )
        out.append("+" * m + "<" * x_cell[i])

    def index_tree(value: int, depth: int, acc: int) -> str:
        # Pointer on j_cell[depth]; both branches return there, zeroed.
        if depth == bits:
            return "+" * (48 + ((value >> acc) & 1)) + ".[-]"
        high = index_tree(value, depth + 1, acc | (1 << (bits - 1 - depth)))
        low = index_tree(value, depth + 1, acc)
        return ">+<[->-<>>" + high + "<<]>[-<>>" + low + "<<>]<"

    def cell_switch(i: int, prefix: list[int], budget: int) -> str:
        # Pointer on x_cell[i] holding v + m; returns there with it zeroed.
        if i == size:
            value = ball_rank(prefix, m)
            delta = x_cell[size - 1] - j_cell[0]
            return "<" * delta + index_tree(value, 0, 0) + ">" * delta

        def case(u: int) -> str:
            v = u - m
            if abs(v) <= budget:
                out = cell_switch(i + 1, [*prefix, v], budget - abs(v))
                if i + 1 < size:
                    out = ">>" + out + "<<"
            else:
                out = "[-]"  # unreachable for valid vectors
            if u == 2 * m:
                return out
            return ">+<[->-<" + case(u + 1) + "]>[-<" + out + ">]<"

        return case(0)

    out.append(">" * x_cell[0] + cell_switch(0, [], m) + "<" * x_cell[0])
    return "".join(out)


def worst_table(n: int, size: int, m: int, bits: int) -> str:
    """Every group spelled by a vector of full norm ``m``: the most marks."""
    k = 1 << bits
    ranks = range(1 << k)
    heavy = max(ranks, key=lambda r: sum(map(abs, ball_unrank(r, size, m))))
    assert sum(map(abs, ball_unrank(heavy, size, m))) == m
    block = "".join(str((heavy >> j) & 1) for j in range(k))
    return block * ((1 << n) >> bits)


def check_layout() -> list[str]:
    """L10  the enumerative lookup: closed form, and it runs."""
    from tests.tools.boolean_runners import run_bf

    lines, rng = [], random.Random(31)
    runs = 0
    for size, m, bits, top_n in ((2, 2, 1, 8), (3, 3, 2, 8), (4, 4, 3, 9)):
        decoder = tree_decoder(size, m, bits)
        for n in range(bits, top_n + 1):
            width = 1 << n
            tables = [worst_table(n, size, m, bits), "0" * width]
            tables.append("".join(rng.choice("01") for _ in range(width)))
            for table in tables:
                program = bf_drawing(table, size, m, bits, 2, decoder)
                for x in range(width):
                    inputs = [str((x >> (n - 1 - j)) & 1) for j in range(n)]
                    assert run_bf(program, inputs) == table[x], (size, m, bits, n, x)
                    runs += 1
    lines.append(f"exhaustive, radix 4, tree decoder: {runs} executions")

    runs = 0
    for size, m, bits, top_n in ((4, 4, 3, 9), (6, 9, 4, 10)):
        decoder = rank_decoder(size, m, bits)
        for n in range(bits, top_n + 1):
            width = 1 << n
            table = "".join(rng.choice("01") for _ in range(width))
            program = bf_drawing(table, size, m, bits, 2, decoder)
            picks = range(width) if n <= 6 else rng.sample(range(width), 24)
            for x in picks:
                inputs = [str((x >> (n - 1 - j)) & 1) for j in range(n)]
                assert run_bf(program, inputs) == table[x], (size, m, bits, n, x)
                runs += 1
    lines.append(f"rank decoder, radix 4: {runs} executions at k = 8, 16")

    for size, m, bits in ((2, 2, 1), (4, 4, 3), (6, 9, 4)):
        decoder = rank_decoder(size, m, bits)
        for radix_bits in (2, 8):
            for n in range(bits, 13):
                table = worst_table(n, size, m, bits)
                marks = ((1 << n) >> bits) * m
                expect = drawing_length(n, size, bits, marks, radix_bits, len(decoder))
                got = len(bf_drawing(table, size, m, bits, radix_bits, decoder))
                assert expect == got, (size, m, bits, n, expect, got)
    lines.append("emitted length matches the closed form, n <= 12, radix 4 and 256")

    # The count at the paper's radix: (S + 1 + M) / k plus the rails and hops,
    # which vanish against T.
    for size, m, bits in ((6, 9, 4), (12, 16, 5), (25, 28, 6)):
        k = 1 << bits
        assert delannoy(size, m) >= 1 << k
        n = 40
        marks = ((1 << n) >> bits) * m
        total = drawing_length(n, size, bits, marks, 8, 0)
        per = total / (1 << n)
        lines.append(f"  (S, M, k) = ({size}, {m}, {k}): {per:.5f} an entry at n = 40")
        assert abs(per - (size + 1 + m) / k) < 3e-3, per  # rails and trailers
    return lines


def check_prices() -> list[str]:
    """L11  the prices and the limit."""
    lines = []
    best: dict[int, tuple[float, int, int]] = {}
    for size in range(1, 60):
        for m in range(1, 60):
            k = int(math.log2(delannoy(size, m)))
            if k >= 1:
                price = (size + m) / k
                if k not in best or price < best[k][0]:
                    best[k] = (price, size, m)
    row = ", ".join(f"k={k}: {best[k][0]:.4f} at {best[k][1:]}" for k in (16, 32, 64))
    lines.append(row)
    assert best[16] == (0.9375, 6, 9), best[16]
    limit = 1 / math.log2(1 + math.sqrt(2))
    assert abs(limit - 0.78644) < 1e-5
    # Central Delannoy numbers grow like (3 + 2 sqrt 2)**n = (1 + sqrt 2)**2n.
    rate = math.log2(delannoy(400, 400)) / 800
    assert abs(rate - math.log2(1 + math.sqrt(2))) < 0.01, rate
    digits = limit / math.log(10)
    lines.append(f"limit {limit:.5f} chars/entry; {digits:.5f} T ln T digits on GRH")
    assert abs(digits - 0.34155) < 1e-5, digits
    return lines


def check_words() -> list[str]:
    """L12  reduced words: the growth rate and the floor it gives."""
    letters = "><+-.,[]"
    forbid = ("+-", "-+", "><", "][", "[]")
    allowed = [
        [float(a != b and a + b not in forbid) for b in letters] for a in letters
    ]
    vector = [1.0] * 8
    for _ in range(500):
        image = [sum(row[j] * vector[j] for j in range(8)) for row in allowed]
        rate = max(image)
        vector = [x / rate for x in image]
    cubic = rate**3 - 4 * rate**2 - 14 * rate - 8
    assert abs(rate - 6.387755) < 1e-6, rate
    assert abs(cubic) < 1e-6, cubic
    floor = 1 / (math.log2(1 + rate) * math.log(10))
    assert abs(floor - 0.150528) < 1e-6, floor
    plain = 1 / (3 * math.log(10))
    return [f"lambda {rate:.5f}, floor {floor:.5f} (from {plain:.5f} with all words)"]


def main() -> int:
    print("L10  the enumerative lookup")
    print("\n".join(check_layout()))
    print("L11 the prices and the limit")
    print("\n".join(check_prices()))
    print("L12 reduced words")
    print("\n".join(check_words()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
