"""Brainfuck decoder for a Delannoy (L1-ball) enumerative code.

A group of ``k = 2**bits`` table bits is one integer ``B < 2**k``, stored on
the tape as the vector ``ball_unrank(B, size, m)`` -- ``size`` signed bytes
with L1 norm at most ``m``.  ``rank_decoder`` emits a fixed program that
re-ranks the vector and prints bit ``j`` of the rank, ``j`` read from stdin.

Layout: the workspace right of the vector is ``m + 1`` blocks of one stride.
Block ``b`` holds ``D(s, m - b)`` for every row ``s`` after a *frame* of
scratch cells.  The frame (rank bytes, counters, the unread vector cells)
carries itself one block right each time the remaining budget ``m'`` drops,
so a table lookup by the runtime index ``m'`` is a fixed offset and no
indexed hop is needed.  Sign tests and carry tests are races of two counters
whose exit position, not a value, tells the outcome (the ``[>]<<`` idiom),
so each costs O(256) steps rather than O(256**2).
"""

from __future__ import annotations

import random
import sys
import time
from collections.abc import Callable
from functools import cache


@cache
def delannoy(s: int, m: int) -> int:
    """Count integer vectors of length ``s`` with L1 norm at most ``m``."""
    if s < 0 or m < 0:
        return 0
    if s == 0 or m == 0:
        return 1
    return delannoy(s - 1, m) + delannoy(s, m - 1) + delannoy(s - 1, m - 1)


def ball_rank(v: list[int], m: int) -> int:
    """Position of v among the vectors of its length with L1 norm <= m.

    Order: position by position; at each position the values are ordered
    0, 1, -1, 2, -2, ...; the count skipped before value w at position i is
    the number of completions of the prefix with that value.
    """
    r, s = 0, len(v)
    for x in v:
        s -= 1  # cells remaining after this one
        a = abs(x)
        if a >= 1:
            r += delannoy(s, m)  # w = 0
            r += 2 * sum(delannoy(s, m - u) for u in range(1, a))  # w = +-u, u < a
            if x < 0:
                r += delannoy(s, m - a)  # w = +a comes before -a
        m -= a
    return r


def ball_unrank(r: int, size: int, m: int) -> list[int]:
    """Inverse of ball_rank."""
    v: list[int] = []
    for i in range(size):
        s = size - 1 - i
        for w in _values(m):
            count = delannoy(s, m - abs(w))
            if r < count:
                v.append(w)
                m -= abs(w)
                break
            r -= count
        else:
            raise ValueError("rank out of range")
    return v


def _values(m: int) -> list[int]:
    """0, 1, -1, 2, -2, ... up to |w| = m -- the per-position order."""
    out = [0]
    for u in range(1, m + 1):
        out += [u, -u]
    return out


class _Emitter:
    """Brainfuck with the pointer tracked relative to a movable frame.

    ``pos`` is the offset from the frame base.  ``shift`` moves the frame's
    live cells one stride right and rebases ``pos``, so code inside a loop
    that shifts the frame stays consistent even though the physical pointer
    position is then runtime-dependent.
    """

    def __init__(self, stride: int) -> None:
        self.stride = stride
        self.pos = 0
        self.out: list[str] = []

    def raw(self, code: str) -> None:
        self.out.append(code)

    def goto(self, off: int) -> None:
        d = off - self.pos
        self.raw(">" * d if d > 0 else "<" * -d)
        self.pos = off

    def add(self, off: int, n: int) -> None:
        self.goto(off)
        # A byte past 128 is shorter as a wrap-around of `-`.
        n %= 256
        self.raw("+" * n if n <= 128 else "-" * (256 - n))

    def clear(self, off: int) -> None:
        self.goto(off)
        self.raw("[-]")

    def begin(self, off: int) -> None:
        self.goto(off)
        self.raw("[")

    def end(self, off: int) -> None:
        self.goto(off)
        self.raw("]")

    def move(self, src: int, dsts: list[tuple[int, int]]) -> None:
        """Drain ``src`` into each (cell, multiplier) of ``dsts``."""
        self.begin(src)
        self.raw("-")
        for d, mult in dsts:
            self.add(d, mult)
        self.end(src)

    def copy(self, src: int, dst: int, tmp: int) -> None:
        self.move(src, [(dst, 1), (tmp, 1)])
        self.move(tmp, [(src, 1)])

    def shift(self, cells: list[int]) -> None:
        """Carry the frame one block right; every other frame cell is 0."""
        s = self.stride
        for c in cells:
            self.begin(c)
            self.raw("-" + ">" * s + "+" + "<" * s + "]")
        self.pos -= s

    def race(
        self,
        p: int,
        body: str,
        on_a: Callable[[], None] | None,
        on_b: Callable[[], None] | None,
    ) -> None:
        """Run ``p[body]`` and branch on where it exited.

        Cells ``p-1``, ``p+2``, ``p+4`` must be 0 and ``p+3`` is the landmark.
        ``body`` starts at ``p`` and ends with ``[>]<<`` from ``p+1``: it
        leaves the pointer at ``p`` (case A, ``p`` just hit 0 with ``p+1``
        still set) or at ``p-1`` (case B, ``p+1`` hit 0).  ``>[-]>>`` clears
        the surviving counter in both cases and lands on the landmark only
        in case A; a second bracket then re-converges the pointer.
        """
        lm = p + 3
        self.add(lm, 1)
        self.goto(p)
        self.raw("[" + body + "]")
        self.raw(">[-]>>")
        self.pos = lm
        self.raw("[")
        if on_a is not None:
            on_a()
        self.goto(lm)
        self.raw("-]>")
        self.pos = lm  # physically p+4 in case A; only case B runs the body
        self.raw("[")
        if on_b is not None:
            on_b()
        self.goto(lm)
        self.raw("->]")
        self.pos = lm + 1


def rank_decoder(size: int, m: int, bits: int) -> str:
    """Brainfuck that prints bit ``j`` of ``ball_rank(v, m)``; see module doc.

    Entry: pointer on a 0 cell W, ``v`` in W+1..W+size as bytes, junk
    beyond.  Reads ``bits`` lines of "0"/"1" (j, MSB first), prints one
    digit.  Correct whenever ``ball_rank(v, m) < 2**(2**bits)``; ``bits``
    is at most 4 since the rank is held in two bytes.
    """
    if not 1 <= bits <= 4:
        raise ValueError("bits must be in 1..4")
    if m > 20:
        raise ValueError("|v_i| <= m must stay below the sign race's half-range")
    # Frame: v_0..v_{size-1}, then the scratch cells below.
    lo, hi, acc, _z0, p, q, _z1, _lm, _z2, t, e2, h2, neg = range(size, size + 13)
    frame = size + 13
    stride = frame + 2 * size
    e = _Emitter(stride)
    e.pos = -1  # W itself; the frame base is W+1

    for c in range(size, (m + 1) * stride):
        e.clear(c)
    # Entries mod 65536: the rank is < 2**16, so the sum is exact mod 2**16.
    for b in range(m + 1):
        for s in range(size):
            d = delannoy(s, m - b) % 65536
            e.add(b * stride + frame + 2 * s, d % 256)
            e.add(b * stride + frame + 2 * s + 1, d // 256)

    def add_pair(elo: int, ehi: int) -> None:
        """(lo, hi) += (elo, ehi), consuming the entry, with carry."""
        e.move(ehi, [(hi, 1)])
        e.begin(elo)  # a zero low byte cannot carry, and the race needs p >= 1
        e.copy(lo, q, t)
        e.add(q, 1)  # q = lo + 1, with 256 read as 0
        e.move(elo, [(lo, 1), (p, -1)])  # p = 256 - elo
        # Both decrement; p runs out first iff lo > 255 - elo, i.e. carry.
        e.race(p, "->-[>]<<", lambda: e.add(hi, 1), None)
        e.end(elo)

    def add_entry(s: int, mult: int) -> None:
        elo = frame + 2 * s
        if mult == 2:
            e.copy(elo, e2, t)
            e.copy(elo + 1, h2, t)
        add_pair(elo, elo + 1)
        if mult == 2:
            add_pair(e2, h2)

    for i in range(size):
        s = size - 1 - i
        live = [lo, hi, acc, neg, *range(i + 1, size)]
        e.move(i, [(p, 1), (q, 1)])
        # p counts down, q counts up: a positive byte zeroes p after |v|
        # steps, a negative one zeroes q after |v| steps; acc counts either.
        e.race(p, "->+<<<+>>>[>]<<", None, lambda: e.add(neg, 1))
        e.begin(acc)
        add_entry(s, 1)  # w = 0
        e.add(acc, -1)
        e.begin(acc)
        e.shift(live)
        add_entry(s, 2)  # w = +-u for 1 <= u < a
        e.add(acc, -1)
        e.end(acc)
        e.shift(live)
        e.begin(neg)
        e.add(neg, -1)
        add_entry(s, 1)  # +a precedes -a
        e.end(neg)
        e.end(acc)

    def read_bit(into: int) -> None:
        e.goto(into)
        e.raw("," + "-" * 48)

    # j = 8 * (top bit) + r for bits == 4; else j = r and hi is unused.
    e.move(lo, [(p, 1)])
    shift_bits = bits
    if bits == 4:
        read_bit(t)
        e.begin(t)
        e.add(t, -1)
        e.clear(p)
        e.move(hi, [(p, 1)])
        e.end(t)
        shift_bits = 3
    for _ in range(shift_bits):
        e.move(q, [(e2, 2)])
        e.move(e2, [(q, 1)])
        read_bit(t)
        e.move(t, [(q, 1)])

    def flip(par: int) -> None:
        e.add(t, 1)
        e.begin(par)
        e.add(par, -1)
        e.add(t, -1)
        e.end(par)
        e.move(t, [(par, 1)])

    # p >>= q, then parity of p: acc is the parity bit, h2 the half.
    e.begin(q)
    e.add(q, -1)
    e.begin(p)
    e.add(p, -1)
    flip(acc)
    e.add(h2, 1)
    e.begin(acc)
    e.add(acc, -1)
    e.add(t, 1)
    e.add(h2, -1)
    e.end(acc)
    e.move(t, [(acc, 1)])
    e.end(p)
    e.clear(acc)  # the parity of the halved value, stale for the next round
    e.move(h2, [(p, 1)])
    e.end(q)
    e.begin(p)
    e.add(p, -1)
    flip(acc)
    e.end(p)
    e.add(acc, 48)
    e.raw(".")
    return "".join(e.out)


def _harness(v: list[int]) -> str:
    """Write ``v`` into cells 1..size and return to cell 0."""
    body = "".join(("+" * x if x >= 0 else "-" * -x) + ">" for x in v)
    return ">" + body + "<" * (len(v) + 1)


def _check(size: int, m: int, bits: int, ranks: list[int]) -> int:
    from tests.tools.boolean_runners import run_bf

    program = rank_decoder(size, m, bits)
    n = 0
    for r in ranks:
        v = ball_unrank(r, size, m)
        assert ball_rank(v, m) == r
        assert max(map(abs, v)) <= m
        for j in range(2**bits):
            digits = [str((j >> b) & 1) for b in reversed(range(bits))]
            got = run_bf(_harness(v) + program, digits)
            want = str((r >> j) & 1)
            assert got == want, (size, m, bits, r, v, j, got, want)
            n += 1
    return n


def main() -> None:
    """Exhaustive small cases, a sampled large one, and the sizes."""
    start = time.monotonic()
    total = 0
    for size, m, bits in [(2, 2, 1), (3, 3, 2), (4, 4, 3)]:
        k = 2**bits
        assert delannoy(size, m) >= 2**k
        for r in range(delannoy(size, m)):
            assert ball_unrank(r, size, m) == ball_unrank(
                ball_rank(ball_unrank(r, size, m), m), size, m
            )
        total += _check(size, m, bits, list(range(2**k)))
    assert delannoy(6, 9) >= 65536
    rng = random.Random(7)
    ranks = [0, 1, 65535, *(rng.randrange(65536) for _ in range(300))]
    total += _check(6, 9, 4, ranks)
    print(f"{total} bit reads checked in {time.monotonic() - start:.1f}s")
    print("len(rank_decoder(4, 4, 3)) =", len(rank_decoder(4, 4, 3)))
    print("len(rank_decoder(6, 9, 4)) =", len(rank_decoder(6, 9, 4)))


if __name__ == "__main__":
    main()
    sys.exit(0)
