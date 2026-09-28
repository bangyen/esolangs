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
arity-dependent part is arithmetic over sums of distinct powers of two,
saturated at the corridor's end (L1),
and the behavioural part is confined to a three-row window whose vocabulary
does not grow with n (L2, L3, L4).

The construction (see the generator's module comment): row ``-1`` is the
*lane*, never painted; row ``0`` is the corridor, white cells ``0..c``
where ``c`` starts the table's trailing run of equal answers (``c = 2**n -
1`` when the last two differ); row ``+1`` holds the answers, cell ``x <= c``
white iff ``table[x] == "1"``.  The head paints that on pass 1 and walks back to the
origin.  Each input is one character, ``n`` (zero: step into the lane) or
``N`` (one: blocked, stay), followed by the template's ``E * 2**(n-1-i)``
walk and ``SN`` return.  A final ``s`` steps onto a black answer; a
white one leaves the ant on the white corridor cell above it.

L1  *Arithmetic.*  A one's walk of ``w`` from column ``x <= c`` ends at
    ``min(x + w, c)`` (L3), so the ant's column after input ``i`` is
    ``min(p_i, c)`` for the partial index ``p_i = sum(bit_k * 2**(n-1-k),
    k <= i)``: ``min(min(p, c) + w, c) = min(p + w, c)`` for ``w >= 0``.
    The final column is ``min(index, c)``, and ``table[min(index, c)] ==
    table[index]`` because every index past ``c`` lies in the run ``c``
    starts.  The partial index never exceeds ``2**n - 1``, checked to n=64
    (the all-ones prefix is the worst, and the bound is arity-monotone past
    it); the saturated recurrence is checked against ``min(index, c)`` for
    every ``c`` and every index to n=8, an identity with no dependence on n.

L2  *The head is what it says.*  After pass 1's head (up to the first run)
    the white cells are exactly the corridor ``0..c`` and its one-answers,
    the ant is at the origin, and ``c`` is where the trailing run starts.
    Traced for every table at n=3 and on a ladder of shaped and random tables
    to n=10.

L3  *Magnitude collapse.*  A zero's walk is blocked at every step because
    the lane is black at every cell, so the walk's length is irrelevant: the
    gadget with ``E * w`` and the gadget with ``E * 1`` leave the ant on the
    same cell for a zero, and a one's walk moves exactly ``w`` on a corridor
    long enough.  On a shorter one it stops at ``c``, blocked at every later
    step because ``(c + 1, 0)`` is black -- the lane's per-step argument
    again, checked for every power-of-two ``c`` and ``w`` through ``2**9``.
    Checked by
    tracing each gadget in isolation on the built grid, every ``w`` that is a
    power of two through ``2**9``.  A zero's separation of column ``w`` from
    the corridor end telescopes the powers to every integer ``2**9`` and
    under, the range the real ladder (n=10) reaches; a walk past it belongs
    to an arity this proof does not exercise, and the collapse is a per-step
    property of a black lane rather than a function of ``w``.

L4  *Motif table.*  Every step of pass 1 and pass 2 is one of a fixed set
    of ``(cycle, phase, command, colour ahead, action)`` motifs, where
    ``cycle`` is the pass number and ``phase`` is the template phase the
    step ran in.  The set is learned at n=5 and replayed at n=6..10: a step
    whose motif is not in the table is a vocabulary growth the finite check
    would have missed.  The same pass also asserts the fixed point (pass 2's
    grid and rest cell equal pass 1's) and the answer.  ``cycle`` replaces an
    earlier ``index // span + 1`` field that was constant ``1`` -- step
    indices repeat per cycle, so pass 2 was never distinguished.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from esolangs.tools.a_painter_ant import a_painter_ant
from esolangs.tools.helpers import TEMPLATE_CHAR
from tests.tools.a_painter_ant_trace import run
from tests.tools.fills import _instantiate_apa

#: Cost band; see ``__main__.py``.  L4's ladder to n=10 is most of it.
BAND = "by-hand"
COST = 15.0


def bits_of(idx: int, n: int) -> list[int]:
    """Input vector for table index ``idx``, most-significant bit first."""
    return [(idx >> (n - 1 - k)) & 1 for k in range(n)]


def corridor_end(table: str) -> int:
    """``c``: the first entry of the table's trailing run of equal answers."""
    return len(table.rstrip(table[-1]))


def expected_grid(table: str) -> dict[tuple[int, int], int]:
    """The white cells the head is meant to paint: corridor and one-answers."""
    end = corridor_end(table)
    grid = {(x, 0): 1 for x in range(end + 1)}
    grid.update({(x, 1): 1 for x in range(end + 1) if table[x] == "1"})
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


def check_l1(max_n: int = 64, max_saturated: int = 8) -> list[str]:
    """Partial indices stay in the table; the saturated walk lands on ``min``.

    The all-ones prefix is the worst partial index at each step, and past it
    the bound is arity-monotone, so the identity at every n to 64 certifies
    the arithmetic for every arity the ladder exercises.  The saturated
    recurrence is checked against ``min(index, c)`` exhaustively to n=8.
    """
    for n in range(1, max_n + 1):
        top = (1 << n) - 1
        partial = 0
        for i in range(n):
            partial += 1 << (n - 1 - i)
            assert 0 <= partial <= top, (n, i)
        assert partial == top, n
    for n in range(1, max_saturated + 1):
        for end in range(1 << n):
            for idx in range(1 << n):
                column = 0
                for bit, i in zip(bits_of(idx, n), range(n), strict=True):
                    column = min(column + bit * (1 << (n - 1 - i)), end)
                assert column == min(idx, end), (n, end, idx)
    return [
        f"  n=1..{max_n}: every partial index stays within the table",
        f"  n=1..{max_saturated}: the saturated walk ends at min(index, c)",
    ]


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
            end = corridor_end(table)
            assert len(set(table[end:])) == 1, (n, table)
            assert end == 0 or table[end - 1] != table[end], (n, table)
        lines.append(f"  n={n}: {len(tables)} tables, head exact")
    return lines


def check_l3(max_w: int = 10) -> list[str]:
    """A zero's walk collapses to nothing; a one's is its exact length.

    Every power-of-two ``w`` through ``2**max_w - 1`` is traced, which the
    alternating template telescopes to every integer the real ladder reaches;
    the collapse is a per-step property of the black lane, so the check is a
    witness of the mechanism rather than a finite ceiling.
    """
    size = 1 << max_w
    # A last answer unlike the one before it keeps the whole corridor.
    build = a_painter_ant("1" * (size - 1) + "0")
    head = build[: build.index(TEMPLATE_CHAR)]
    powers = [1 << k for k in range(max_w)]
    for w in powers:
        for bit, spelled in ((0, "n"), (1, "N")):
            outcome = run(head + spelled + "E" * w + "SN", 1)
            assert outcome.position == (w if bit else 0, 0), (w, bit)
            if bit == 0:
                assert run(head + "nESN", 1).position == outcome.position
    for end in powers:
        short = a_painter_ant("1" * end + "0" * (size - end))
        head = short[: short.index(TEMPLATE_CHAR)]
        for w in powers:
            outcome = run(head + "N" + "E" * w + "SN", 1)
            assert outcome.position == (min(w, end), 0), (end, w)
    return [
        f"  w=1..{size // 2}: zero walks collapse, one walks measure exactly",
        f"  c, w=1..{size // 2}: a one's walk stops at the corridor's end c",
    ]


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
            assert rest[i:] == "s", rest[i:]
            out.append("read")
            i += 1
    assert len(out) == len(template)
    return out


Motif = tuple[int, str, str, int | None, str]


def motifs_of(table: str, idx: int, n: int) -> tuple[set[Motif], bool, bool]:
    """Every motif of passes 1 and 2, the fixed-point verdict, and the answer.

    The pass number is ``step_index // len(program) + 1`` over the *concatenated
    two-cycle* step list, which is what distinguishes pass 1 from pass 2;
    ``Step.index`` alone is the within-cycle index (``i % length``) and so is
    constant ``0..length-1`` on both passes.
    """
    template = a_painter_ant(table)
    names = phases(template)
    program = _instantiate_apa(template, bits_of(idx, n))
    first = run(program, 1)
    second = run(program, 2)
    span = len(program)
    grid: dict[tuple[int, int], int] = {}
    seen: set[Motif] = set()
    for position, step in enumerate(second.steps):
        cycle = position // span + 1
        ahead = grid.get(step.target, 0) if step.target is not None else None
        seen.add((cycle, names[step.index], step.command, ahead, step.action))
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
