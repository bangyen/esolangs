"""The seventeen-input group address, as a word-level model of the fold.

    uv run python scripts/malbolge17/address17.py

Fourteen address bits ``x1..x14`` (``x15..x17`` pick the row within a group)
map to 16,384 distinct groups of three cells in the seven-box tiling of
docs/proofs/malbolge-scaling.md, with cells ``0..6561`` one free run.  The
fold is the shipped gadget (``_GADGET``) plus crazy/rot steps, each of which a
source string can execute; this script checks the map, not an emitted program.

* Triples T1..T4 are ``x3..x5``, ``x6..x8``, ``x9..x11``, ``x12..x14``.
* Case A (``x1 = 1``, ``z`` from ``x2``) and B (``x1x2 = 01``): slots 0-2 take
  T1-T3, the top slot T4.  Special rows (``x1x2 = 00``): ``x12x13`` picks C1-C3
  or D, ``x14`` is C's ``z`` bit or D's 1/2; the pinned slot takes a gadget run
  on all-0 reads and the top takes the pinned slot's own triple.
* Accumulator from all-2; each lower slot mixes ``crazy(all-2, v)`` then ``u``
  (``p`` over the cell with ``A = acc``, then ``*``); slots 0 and 1 swap12
  their ``u`` first and slot 2 its ``v``.  ``z`` mixes a cell ``zbase + z``.
  The top mixes
  ``crazy(all-2, v)``, then enters ``u`` the other way round
  (``acc = crazy(crazy(all-2, u), acc)``, then ``*``), both swapped first.
* Tail: swap01, swap12, ``p`` with all-1 and trit 0 = 2; state pointers are
  ``crazy(Q, acc)`` for ``Q`` all-2 with trit 0 in {0, 1, 2}; cells are
  pointer + 1.
"""

from __future__ import annotations

from esolangs.interpreters.other.malbolge import _crazy
from esolangs.tools._malbolge_core import _rot
from esolangs.tools._malbolge_digits import _GADGET, _K

W = 59049
ALL1, ALL2 = 29524, 59048
LOW, PIN = (33, 33, 78), (38, 38, 38)
ZBASE = 29514
Z_A = (1, 2)
Z_B = 0
Z_C = (1, 2)


def gadget(init: tuple[int, int, int], reads: list[int]) -> tuple[int, int]:
    """Run the shipped gadget on walked cells ``init``; return ``(u, v)``."""
    cells, a, it = list(init), 0, iter(reads)
    for op in _GADGET:
        if op == "/":
            a = next(it)
        elif op[0] == "K":
            a = _K[int(op[1])]
        else:
            a = cells[int(op)] = _crazy(a, cells[int(op)])
    return cells[1], cells[2]


def mix(acc: int, cell: int) -> int:
    """``p`` over ``cell`` with ``A = acc``, then ``*`` there."""
    return _rot(_crazy(acc, cell))


def swap(x: int) -> int:
    """``p`` with ``A = 2``: trit 0 swaps 1 and 2, 1s and 2s elsewhere stay."""
    return _crazy(2, x)


def group_word(bits: list[int]) -> int:
    """Return the accumulator after the tail for address bits ``x1..x14``."""
    triples = [tuple(bits[2 + 3 * k : 5 + 3 * k]) for k in range(4)]
    normal = [gadget(LOW, [48 + b for b in t]) for t in triples[:3]]
    if bits[0]:
        z, slots, top = Z_A[bits[1]], normal, triples[3]
    elif bits[1]:
        z, slots, top = Z_B, normal, triples[3]
    else:
        sel = 2 * triples[3][0] + triples[3][1]
        k, z = (sel, Z_C[triples[3][2]]) if sel < 3 else (triples[3][2], Z_B)
        slots, top = list(normal), triples[k]
        slots[k] = gadget(PIN, [0, 0, 0])
    acc = ALL2
    for j, (u, v) in enumerate(slots):
        u = swap(u) if j < 2 else u
        v = swap(v) if j == 2 else v
        acc = mix(mix(acc, _crazy(ALL2, v)), u)
    acc = mix(acc, ZBASE + z)
    u, v = gadget(LOW, [48 + b for b in top])
    acc = _rot(_crazy(_crazy(ALL2, swap(u)), mix(acc, _crazy(ALL2, swap(v)))))
    return _crazy(_crazy(ALL2, _crazy(acc, ALL1)), ALL1 + 1)


def main() -> None:
    """Check the map: distinct groups, no wrap, and the free runs."""
    words = [
        group_word([(r >> (13 - k)) & 1 for k in range(14)]) for r in range(1 << 14)
    ]
    cells = {(_crazy(ALL2 - 2 + q, w) + 1) % W for w in words for q in range(3)}
    free = [a not in cells for a in range(W)]
    runs, start = [], None
    for a, f in enumerate([*free, False]):
        if f and start is None:
            start = a
        elif not f and start is not None:
            runs.append(a - start)
            start = None
    print(f"distinct groups {len(set(words))}, table cells {len(cells)}")
    print(f"lowest table cell {min(cells)}, longest free runs {sorted(runs)[-9:]}")
    print(f"free cells in runs of 200 or more: {sum(r for r in runs if r >= 200)}")
    windows = [
        b
        for b in range(243)
        if all((b // 3**k) % 3 < 2 for k in range(5))
        and not any(b * 243 + o in cells for o in range(243))
    ]
    print(f"table-free landing windows (243-blocks, top trits 0/1): {windows}")


if __name__ == "__main__":
    main()
