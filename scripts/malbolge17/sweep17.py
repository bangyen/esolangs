"""Build a valid seventeen-input Malbolge program that first-reads almost all memory.

The program prints input 2 on every row, yet before that one output it
executes 29,564 cells and reads 29,433 more as data -- a first-read weight of
about 164,965 bits, above the 131,050 of the output-truncated count.  So a
per-program weight bound cannot hold (see "Seventeen: the read-count route" in
docs/proofs/malbolge-scaling.md).

    uv run python scripts/malbolge17/sweep17.py OUT.mb

Layout: nops from 0 (cell 57 is a ``/``), then ``*`` at 114 turns that cell into
39403 and two ``j``s send ``d`` there; ``p``s at 117.. read 39404.. in
lockstep.  A ``*``/``j``/``p``/``j``/``j`` gadget through the low cells 51..57
writes 29564 into cell 56 and jumps ``d`` to it; a second ``p`` sweep reads
29565..39395; ``/ < v`` prints the next input and halts.
"""

from __future__ import annotations

import sys

from esolangs.interpreters.other.malbolge import _XLAT2, _crazy
from esolangs.tools.malbolge.core import _char_for, _f, _rot

W = 59049


def build() -> str:
    """Return the program source, one character per cell."""
    src = [_f(h) for h in range(W)]

    def put(h: int, op: str) -> None:
        src[h] = _char_for(op, h)

    def g(h: int) -> int:  # value after the cell has run once
        return ord(_XLAT2[src[h] - 33])

    put(57, "/")
    put(114, "*")
    put(115, "j")
    assert src[115] == 113  # the j lands d on 114, which now holds rot(113)
    put(116, "j")
    c, m1 = 117, 19600
    for _ in range(m1):
        put(c, "p")
        c += 1
    q = 39404 + m1  # first untouched cell after window A
    src[q], src[q + 1] = 126, 50  # both decode (checked by the loader)
    z = 56
    put(c, "*")
    put(c + 1, "j")
    c, d = c + 2, 51
    while d < z:
        c, d = c + 1, d + 1
    put(c, "p")  # cell z := crazy(rot(126), g(z))
    p = _crazy(_rot(126), g(z))
    put(c + 1, "j")  # d := g(z + 1) + 1, then nops walk it back up to z
    c, d = c + 2, g(z + 1) + 1
    while d < z:
        c, d = c + 1, d + 1
    put(c, "j")
    c += 1
    m2 = min(p + 1 - c - 3, 39403 - p)
    for _ in range(m2):
        put(c, "p")
        c += 1
    put(c, "/")
    put(c + 1, "<")
    put(c + 2, "v")
    return "".join(map(chr, src))


if __name__ == "__main__":
    with open(sys.argv[1], "w") as out:
        out.write(build())
