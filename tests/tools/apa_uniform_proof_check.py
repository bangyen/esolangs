"""Machine checks backing the A Painter Ant uniform-in-n correctness proof.

Run:  just apa-proof   (or python tests/tools/apa_uniform_proof_check.py)

Each check corresponds to a lemma in the relevant generator tests.

**Run it by hand when A Painter Ant's head, body, or routing changes** --
that is what invalidates the motif table, and re-running this is how it is
caught.  Nothing runs it for you: it is 1m20s single-threaded, against 2.5
minutes for the whole suite under ``-n auto``, so neither pytest (no
``test_`` prefix, so it is not collected) nor CI pays that on every push for
inputs that move this rarely.

It sits here rather than in ``scripts/`` beside ``arrowqueue_lemmas.py``,
its opposite number for ArrowQueue, because of what it imports: those
lemmas reach only into ``esolangs``, while this shares
``tests.tools.a_painter_ant_trace`` with ``test_boolean_grid.py``.  A
``scripts/`` module importing from ``tests/`` would invert that dependency,
and mypy checks ``scripts`` but not ``tests``.

What it buys over the suite is the *uniform-in-n* half.  The checked-in
tests cover the shipped behaviour at the arities they can enumerate; this
reduces "all tables at every arity" to a finite computation, in the style of
the relevant tests: the arity-dependent part is arithmetic over signed sums of
distinct powers of two (L1, L2), and the behavioural part is confined to a
bounded window whose vocabulary does not grow with n (L3, L4).

L4 and L4b are stated over the head's *shared prefix* states.  ``_head``
paints every white leaf in one depth-first walk, sharing common prefixes and
pruning all-zero subtrees, so a leaf owns neither a standalone block nor the
``rev`` edges that unwind the prefix it shares with its siblings.  The units
here are that emission order, the rest point is checked at each leaf's paint,
and a motif is keyed on the state its unit is entered in -- never on the leaf,
and never on the span, which is what lets a table learned at n=5 replay at
arities whose edges are exponentially longer.

Note the programs are built by :func:`tree_program`, not by
``a_painter_ant``: the shipped generator dispatches to the linear answer strip
above ``2**n > 16``, which has no head at all, and these are head lemmas.
"""

from __future__ import annotations

import itertools
import random
import sys
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from esolangs.tools.a_painter_ant import (
    _bit_is_horizontal,
    _bit_move,
    _body,
    _head,
    _instantiate_apa,
    _leaf_positions,
    _reverse_moves,
)
from tests.tools.a_painter_ant_trace import run

_D = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}

#: One unit of the shared head: (kind, horizontal, bit, non-space length).
Unit = tuple[str, bool | None, int | None, int]


def bits_of(idx: int, n: int) -> list[int]:
    """Input vector for table index ``idx``, most-significant bit first."""
    return [(idx >> (n - 1 - k)) & 1 for k in range(n)]


def _move_targets(n: int, bits: list[int]) -> list[tuple[int, int]]:
    """Every cell the head's outbound walk to a leaf moves onto."""
    x = y = 0
    out = []
    for k, b in enumerate(bits):
        for c in _bit_move(n, k, b):
            dx, dy = _D[c]
            x += dx
            y += dy
            out.append((x, y))
    return out


def tree_program(table: str, idx: int, n: int) -> str:
    """Instantiate the *tree* route for ``table`` at any arity.

    :func:`a_painter_ant` dispatches to the linear answer strip above
    ``2**n > 16``, so calling it would hand back a program with no head at
    exactly the arities these head lemmas are about.  This mirrors the
    ``<= 16`` branch instead, which is the route the ledger's `Size dispatch`
    paragraph promises is available at every arity.  ``_instantiate_apa``
    picks its branch off the template's ``sS`` suffix, so a tree template
    routes through the weighted embedding on its own.
    """
    head = _head(table, [0] * n)
    prefix = "".join("{X" + str(i) + "}" for i in range(n - 1))
    suffix = "{X" + str(n - 1) + "}"
    return _instantiate_apa(head + prefix + _body() + suffix, bits_of(idx, n))


def head_units(table: str, n: int) -> list[Unit]:
    """Split the shared head into units, in emission order.

    This mirrors :func:`_head`'s depth-first ``walk`` rather than enumerating
    one independent block per leaf.  The head shares every common prefix and
    omits all-zero subtrees, so a leaf's route is no longer a standalone
    ``outbound + P + reverse`` block: an ``out`` edge is entered from whatever
    state its parent left, and one ``rev`` edge is shared by every leaf under
    it.  The units are that emission order, and they tile the head exactly --
    :func:`check_units_tile` is the assertion that they do.

    ``kind`` is one of ``N``/``lead``/``out``/``P``/``rev``/``revlead``/
    ``end``; ``horizontal`` and ``bit`` are the axis and branch of an
    ``out``/``rev`` edge and ``None`` elsewhere.
    """
    units: list[Unit] = [("N", None, None, 1)]
    lead = "WS" if n >= 3 and n % 2 == 1 else ""
    if lead:
        units.append(("lead", None, None, len(lead)))

    def walk(start: int, stop: int, depth: int) -> None:
        if "1" not in table[start:stop]:
            return
        if depth == n:
            units.append(("P", None, None, 1))
            return
        middle = (start + stop) // 2
        for bit, lo, hi in ((0, start, middle), (1, middle, stop)):
            if "1" not in table[lo:hi]:
                continue
            horizontal = _bit_is_horizontal(n, depth)
            edge = ""
            if n >= 2:
                edge = "NE" if horizontal else "WS"
            edge += _bit_move(n, depth, bit)
            units.append(("out", horizontal, bit, len(edge)))
            walk(lo, hi, depth + 1)
            units.append(("rev", horizontal, bit, len(_reverse_moves(edge))))

    walk(0, len(table), 0)
    if lead:
        units.append(("revlead", None, None, len(lead)))
    units.append(("end", None, None, 3))
    return units


def check_units_tile(table: str, n: int) -> None:
    """Assert the unit stream accounts for every head character."""
    total = sum(span for _kind, _h, _b, span in head_units(table, n))
    head = len(_head(table, [0] * n))
    assert total == head, f"units cover {total} of {head} head chars at n={n}"


def check_l1(max_n: int = 12) -> list[str]:
    """L1: leaves are distinct and pairwise >= 4 apart (Chebyshev)."""
    lines = []
    for n in range(1, max_n + 1):
        pts = [(x, y) for x, y, _ in _leaf_positions(n)]
        assert len(set(pts)) == len(pts), f"leaf collision at n={n}"
        sep = min(
            max(abs(a[0] - b[0]), abs(a[1] - b[1]))
            for a, b in itertools.combinations(pts, 2)
        )
        assert sep >= 4, f"separation {sep} < 4 at n={n}"
        lines.append(f"  n={n:2d}: {len(pts):5d} leaves, min separation {sep}")
    return lines


def check_l2(max_n: int = 9) -> list[str]:
    """L2: no head move target is a foreign leaf, so paint cannot block it."""
    lines = []
    for n in range(1, max_n + 1):
        leafset = {(x, y) for x, y, _ in _leaf_positions(n)}
        on_leaf = 0
        mind = 10**9
        for x, y, bits in _leaf_positions(n):
            own = (x, y)
            for c in _move_targets(n, list(bits))[:-1]:
                if c in leafset and c != own:
                    on_leaf += 1
                mind = min(
                    mind,
                    min(
                        max(abs(c[0] - lx), abs(c[1] - ly))
                        for (lx, ly) in leafset
                        if (lx, ly) != own
                    ),
                )
        assert on_leaf == 0, f"head walks onto a foreign leaf at n={n}"
        lines.append(
            f"  n={n}: targets on a foreign leaf {on_leaf}, min distance {mind}"
        )
    return lines


def check_l3() -> list[str]:
    """L3: a run blocked on its first character is a no-op at any length."""
    lines = []
    for ch in "NSEW":
        base = None
        for length in (1, 2, 4, 8, 16, 64, 256, 1024):
            outcome = run("P" + ch * length, 1)
            fired = sum(1 for s in outcome.steps if s.action == "moved")
            assert fired == 0, f"{ch}x{length} fired {fired}"
            if base is None:
                base = outcome.position
            assert outcome.position == base, f"{ch}x{length} drifted"
        lines.append(f"  {ch}: blocked at every length up to 1024, position fixed")
    return lines


def check_l4(table: str, idx: int, n: int) -> tuple[bool, bool, bool, bool, int]:
    """L4 invariants for one program.

    Returns (I2 rest point, I3 zero paint, I4 fixed point, correctness,
    cycle-2 radius).

    I2 is stated at the leaf paints rather than at block ends.  Under the
    shared head a leaf has no block of its own to end, but every ``P`` is
    still reached with the ant parked one cell north of its cycle-1 landing,
    and the paint re-whitens an already-white cell.  That is the property the
    old per-leaf rest point was a special case of.
    """
    prog = tree_program(table, idx, n)
    length = len([c for c in prog if not c.isspace()])
    first = run(prog, 1)
    second = run(prog, 2)
    lx, ly = first.position
    steps2 = second.steps[length:]

    pos = 0
    rest_ok = True
    paints = 0
    for kind, _horizontal, _bit, span in head_units(table, n):
        seg = steps2[pos : pos + span]
        pos += span
        if kind != "P":
            continue
        paints += 1
        step = seg[0]
        parked = (step.position[0] - lx, step.position[1] - ly) == (0, -1)
        if not parked or first.grid.get(step.position) != 1:
            rest_ok = False
    if paints != table.count("1"):
        rest_ok = False

    zero_paint = first.grid == second.grid
    fixed = second.position == first.position
    correct = first.landing_colour() == int(table[idx])
    radius = max(max(abs(s.position[0] - lx), abs(s.position[1] - ly)) for s in steps2)
    return rest_ok, zero_paint, fixed, correct, radius


def motif_pass(
    table: str, idx: int, n: int, motifs: dict, errors: list, *, learn: bool
) -> int:
    """Learn or replay the per-unit motif table for one program's cycle 2.

    A motif is keyed on the state the unit is *entered* in, not on the leaf it
    belongs to: ``(kind, horizontal, bit, leaf_white, entry)``.  That is what
    makes the decomposition survive prefix sharing -- a shared ``out`` edge is
    entered once but left toward several subtrees, and a ``rev`` edge unwinds
    a prefix many leaves used, so neither can be attributed to one leaf.

    The span is deliberately *not* part of the key.  Cycle 2 fires only a
    unit's two uppercase anchor characters and blocks its whole lowercase run
    (L3), so the exit state is fixed by the entry state and the axis however
    long the edge is -- that is the magnitude collapse, and it is why a table
    learned at one arity replays at arities whose edges are exponentially
    longer.  Returns the number of units checked.
    """
    prog = tree_program(table, idx, n)
    length = len([c for c in prog if not c.isspace()])
    first = run(prog, 1)
    second = run(prog, 2)
    lx, ly = first.position
    steps2 = second.steps[length:]
    leaf_white = first.grid.get((lx, ly), 0) == 1

    pos = 0
    cur: tuple[int, int] | None = None
    checked = 0
    for kind, horizontal, bit, span in head_units(table, n):
        seg = steps2[pos : pos + span]
        pos += span
        entry = (seg[0].position[0] - lx, seg[0].position[1] - ly)
        exit_ = (seg[-1].position[0] - lx, seg[-1].position[1] - ly)
        fired_low = sum(1 for s in seg if s.command.islower() and s.action == "moved")
        if cur is None:
            cur = entry
        key = (kind, horizontal, bit, leaf_white, cur)
        checked += 1
        if learn:
            if key in motifs and motifs[key] != (exit_, fired_low):
                errors.append(("conflict", key, n))
            motifs[key] = (exit_, fired_low)
        else:
            got = motifs.get(key)
            if got is None:
                errors.append(("missing", key, n))
            elif got != (exit_, fired_low):
                errors.append(("wrong", key, got, (exit_, fired_low), n))
                return checked
        cur = exit_
    return checked


def main() -> int:
    random.seed(41)
    print("L1  leaf separation >= 4 (arithmetic, all n)")
    print("\n".join(check_l1()))
    print("\nL2  head walks never target a foreign leaf (arithmetic, all n)")
    print("\n".join(check_l2()))
    print("\nL3  magnitude collapse: a blocked run is a no-op at any length")
    print("\n".join(check_l3()))

    print("\nL4  cycle-2 invariants (I2 rest point, I3 zero paint, I4 fixed point)")
    fails = [0] * 4
    for v in range(256):
        table = format(v, "08b")
        for idx in range(8):
            rest, zero, fixed, correct, radius = check_l4(table, idx, 3)
            for j, ok in enumerate((rest, zero, fixed, correct)):
                fails[j] += not ok
            assert radius <= 2
    print(f"  n=3 exhaustive (256 tables x 8 inputs): failures {fails}")
    assert fails == [0, 0, 0, 0]

    for n in range(4, 9):
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
        for _ in range(6):
            tables.append("".join(random.choice("01") for _ in range(size)))
        fails = [0] * 4
        worst = 0
        total = 0
        step = max(1, size // 16)
        for table in tables:
            for idx in range(0, size, step):
                total += 1
                rest, zero, fixed, correct, radius = check_l4(table, idx, n)
                for j, ok in enumerate((rest, zero, fixed, correct)):
                    fails[j] += not ok
                worst = max(worst, radius)
        print(
            f"  n={n}: {total} programs over {len(tables)} tables, "
            f"failures {fails}, max radius {worst}"
        )
        assert fails == [0, 0, 0, 0]

    print("\nL4b motif table: learned at n=5, replayed at unseen arities")
    motifs: dict = {}
    errors: list = []
    size = 32
    tables = [
        "1" * size,
        "0" * size,
        "".join(str(bin(i).count("1") % 2) for i in range(size)),
    ]
    for _ in range(4):
        tables.append("".join(random.choice("01") for _ in range(size)))
    learned_units = 0
    for table in tables:
        check_units_tile(table, 5)
        for idx in range(size):
            learned_units += motif_pass(table, idx, 5, motifs, errors, learn=True)
    # Magnitude collapse is a claim about the units whose span grows with n:
    # the edges.  The fixed "N" prefix and "Ssn" tail are constant-length
    # framing that does fire (that is the cycle-2 dance landing), so they are
    # reported separately rather than folded into the claim.
    grown = {"out", "rev"}
    fired = {v[1] for k, v in motifs.items() if k[0] in grown}
    fired_tail = {v[1] for k, v in motifs.items() if k[0] not in grown}
    entries = {k[4] for k in motifs}
    print(f"  learned {len(motifs)} entries from n=5, conflicts {len(errors)}")
    print(f"  units decomposed: {learned_units}")
    print(f"  lowercase steps fired inside an edge unit: {sorted(fired)}")
    print(f"  lowercase steps fired inside the fixed framing: {sorted(fired_tail)}")
    print(f"  entry offsets: {sorted(entries)}")
    assert not errors
    assert fired == {0}, f"an arity-dependent edge fired a lowercase move: {fired}"
    assert learned_units > 0
    assert grown <= {k[0] for k in motifs}, "no edge motifs learned"

    for n in range(6, 10):
        size = 1 << n
        tables = [
            "1" * size,
            "0" * size,
            "".join(str(bin(i).count("1") % 2) for i in range(size)),
            "1" + "0" * (size - 1),
            "0" * (size - 1) + "1",
        ]
        for _ in range(3):
            tables.append("".join(random.choice("01") for _ in range(size)))
        before = len(errors)
        checked = 0
        units = 0
        step = max(1, size // 8)
        for table in tables:
            check_units_tile(table, n)
            for idx in range(0, size, step):
                checked += 1
                units += motif_pass(table, idx, n, motifs, errors, learn=False)
        print(
            f"  n={n}: {checked} programs replayed, {units} units, "
            f"prediction errors {len(errors) - before}"
        )
        assert len(errors) == before
        assert units > checked, f"no shared-head units replayed at n={n}"

    print("\nall lemma checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
