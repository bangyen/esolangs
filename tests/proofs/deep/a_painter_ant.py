"""Machine checks backing the A Painter Ant uniform-in-n correctness proof.

Run:  just apa-proof   (or python tests/proofs/deep/a_painter_ant.py)

**Run it by hand when A Painter Ant's head or routing changes** -- that is
what invalidates the motif table, and re-running this is how it is caught.
It is a few seconds now; it was 1m20s when the generator had a tree route
whose head lemmas needed a foreign-leaf sweep at n=9.

It sits beside ``arrowqueue.py``, its opposite number for ArrowQueue,
under ``tests/proofs/deep/``: both are hand-derived uniform-in-n arguments
rather than the registry-wide obligations one directory up.  Neither can
live in ``scripts/`` -- this one shares ``tests.tools.a_painter_ant_trace``
with ``test_boolean_grid.py``, and a ``scripts/`` module importing from
``tests/`` would invert that dependency, since mypy checks ``scripts`` but
not ``tests``.

What it buys over the suite is the *uniform-in-n* half.  The checked-in
tests cover the shipped behaviour at the arities they can enumerate; this
reduces "all tables at every arity" to a finite computation: the
arity-dependent part is arithmetic over sums of distinct powers of two (L1),
and the behavioural part is confined to a three-row window whose vocabulary
does not grow with n (L2, L3, L4).

The construction (see the generator's module comment): row ``-1`` is the
*lane*, never painted; row ``0`` is the corridor, ``2**n`` white cells from
``x = 0``; row ``+1`` holds the answers, cell ``x`` white iff
``table[x] == "1"``.  The head paints that on pass 1 and walks back to the
origin.  Each input is one character, ``n`` (zero: step into the lane) or
``N`` (one: blocked, stay), followed by the template's ``E * 2**(n-1-i)``
walk and ``SN`` return.

L1  *Arithmetic.*  The ant's column after input ``i`` is the partial index
    ``sum(bit_k * 2**(n-1-k), k <= i)``, which never exceeds ``2**n - 1``,
    the corridor's last cell -- so no walk runs off the corridor's end and
    the final column is the table index.  Checked as an identity to n=64.

L2  *The head is what it says.*  After pass 1's head (up to the first run)
    the white cells are exactly the corridor and the one-answers, and the
    ant is at the origin.  Traced for every table at n=3 and on a ladder of
    shaped and random tables to n=10.

L3  *Magnitude collapse.*  A zero's walk is blocked at every step because
    the lane is black at every cell, so the walk's length is irrelevant: the
    gadget with ``E * w`` and the gadget with ``E * 1`` leave the ant on the
    same cell for a zero, and a one's walk moves exactly ``w``.  Checked by
    tracing each gadget in isolation on the built grid, every ``w`` to 2**9.

L4  *Motif table.*  Every step of pass 1 and pass 2 is one of a fixed set
    of ``(phase, command, colour ahead, action)`` motifs.  The set is learned
    at n=5 and replayed at n=6..10: a step whose motif is not in the table is
    a vocabulary growth the finite check would have missed.  The same pass
    also asserts the fixed point (pass 2's grid and rest cell equal pass
    1's) and the answer.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from esolangs.tools.a_painter_ant import _instantiate_apa, a_painter_ant
from esolangs.tools.helpers import TEMPLATE_CHAR
from tests.tools.a_painter_ant_trace import run

#: Cost band; see ``__main__.py``.  L4's ladder to n=10 is most of it.
BAND = "by-hand"
COST = 15.0


def bits_of(idx: int, n: int) -> list[int]:
    """Input vector for table index ``idx``, most-significant bit first."""
    return [(idx >> (n - 1 - k)) & 1 for k in range(n)]


def expected_grid(table: str) -> dict[tuple[int, int], int]:
    """The white cells the head is meant to paint: corridor and one-answers."""
    grid = {(x, 0): 1 for x in range(len(table))}
    grid.update({(x, 1): 1 for x, bit in enumerate(table) if bit == "1"})
    return grid


def ladder(n: int, rng: random.Random, extra: int = 6) -> list[str]:
    """Shaped tables at arity ``n`` plus ``extra`` random ones."""
    size = 1 << n
    tables = [
        "0" * size,
        "1" * size,
        "1" + "0" * (size - 1),
        "0" * (size - 1) + "1",
        "".join(str(bin(i).count("1") % 2) for i in range(size)),
        "01" * (size // 2),
        "10" * (size // 2),
    ]
    tables.extend("".join(rng.choice("01") for _ in range(size)) for _ in range(extra))
    return tables


def check_l1(max_n: int = 64) -> list[str]:
    """Partial indices are bounded by the corridor at every arity."""
    for n in range(1, max_n + 1):
        top = (1 << n) - 1
        # The largest partial index at every prefix length is the all-ones
        # prefix, and its last (full) value is the corridor's end.
        partial = 0
        for i in range(n):
            partial += 1 << (n - 1 - i)
            assert 0 <= partial <= top, (n, i)
        assert partial == top, n
    return [f"  n=1..{max_n}: every partial index stays on the corridor"]


def check_l2(max_n: int = 10) -> list[str]:
    """The head paints exactly the corridor and the answers, then rests at 0."""
    rng = random.Random(7)
    lines = []
    for n in range(1, max_n + 1):
        tables = (
            [format(v, f"0{1 << n}b") for v in range(1 << (1 << n))]
            if n <= 3
            else ladder(n, rng)
        )
        for table in tables:
            template = a_painter_ant(table)
            head = template[: template.index(TEMPLATE_CHAR)]
            outcome = run(head, 1)
            white = {cell for cell, colour in outcome.grid.items() if colour == 1}
            assert white == set(expected_grid(table)), (n, table)
            assert outcome.position == (0, 0), (n, table)
        lines.append(f"  n={n}: {len(tables)} tables, head exact")
    return lines


def check_l3(max_w: int = 10) -> list[str]:
    """A zero's walk collapses to nothing at any length; a one's is its length."""
    size = 1 << max_w
    build = a_painter_ant("1" * size)
    head = build[: build.index(TEMPLATE_CHAR)]
    for w in [1 << k for k in range(max_w)]:
        for bit, spelled in ((0, "n"), (1, "N")):
            outcome = run(head + spelled + "E" * w + "SN", 1)
            assert outcome.position == (w if bit else 0, 0), (w, bit)
            # And the short gadget agrees with the long one for a zero.
            if bit == 0:
                assert run(head + "nESN", 1).position == outcome.position
    return [f"  w=1..{size // 2}: zero walks collapse, one walks measure exactly"]


def phases(template: str) -> list[str]:
    """Name each template position: ``head``, ``run``, ``walk``, ``ret``, ``read``."""
    out: list[str] = []
    first = template.index(TEMPLATE_CHAR)
    out.extend(["head"] * first)
    rest = template[first:]
    i = 0
    while i < len(rest):
        if rest[i] == TEMPLATE_CHAR:
            out.append("run")
            i += 1
        elif rest[i] == "E":
            out.append("walk")
            i += 1
        elif rest[i : i + 2] == "SN":
            out.extend(["ret", "ret"])
            i += 2
        else:
            assert rest[i:] == "sS", rest[i:]
            out.extend(["read", "read"])
            i += 2
    assert len(out) == len(template)
    return out


Motif = tuple[int, str, str, int | None, str]


def motifs_of(table: str, idx: int, n: int) -> tuple[set[Motif], bool, bool]:
    """Every motif of passes 1 and 2, the fixed-point verdict, and the answer."""
    template = a_painter_ant(table)
    names = phases(template)
    program = _instantiate_apa(template, bits_of(idx, n))
    first = run(program, 1)
    second = run(program, 2)
    grid: dict[tuple[int, int], int] = {}
    seen: set[Motif] = set()
    span = len(program)
    for step in second.steps:
        ahead = grid.get(step.target, 0) if step.target is not None else None
        seen.add(
            (
                step.index // span + 1,
                names[step.index % span],
                step.command,
                ahead,
                step.action,
            )
        )
        if step.action == "paint_white":
            grid[step.position] = 1
        elif step.action == "paint_black":
            grid[step.position] = 0
    stable = second.grid == first.grid and second.position == first.position
    correct = second.landing_colour() == int(table[idx])
    return seen, stable, correct


def main() -> int:
    rng = random.Random(41)
    print("L1  partial index bounded by the corridor (arithmetic, all n)")
    print("\n".join(check_l1()))
    print("\nL2  head paints exactly the corridor and the answers")
    print("\n".join(check_l2()))
    print("\nL3  magnitude collapse: a blocked walk is a no-op at any length")
    print("\n".join(check_l3()))

    print("\nL4  motif table learned at n<=5, replayed at n=6..10; fixed point; answer")
    learned: set[Motif] = set()
    for n in range(1, 6):
        tables = (
            [format(v, f"0{1 << n}b") for v in range(1 << (1 << n))]
            if n <= 3
            else ladder(n, rng)
        )
        for table in tables:
            for idx in range(1 << n):
                seen, stable, correct = motifs_of(table, idx, n)
                assert stable, (n, table, idx)
                assert correct, (n, table, idx)
                learned |= seen
        print(
            f"  n={n}: {len(tables)} tables x {1 << n} rows, "
            f"motifs so far {len(learned)}"
        )

    for n in range(6, 11):
        size = 1 << n
        tables = ladder(n, rng)
        step = max(1, size // 16)
        unseen: set[Motif] = set()
        total = 0
        for table in tables:
            for idx in [*range(0, size, step), size - 1]:
                total += 1
                seen, stable, correct = motifs_of(table, idx, n)
                assert stable, (n, table, idx)
                assert correct, (n, table, idx)
                unseen |= seen - learned
        print(
            f"  n={n}: {total} programs over {len(tables)} tables, "
            f"unseen motifs {len(unseen)}"
        )
        assert not unseen, sorted(unseen)
    print("\nOK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
