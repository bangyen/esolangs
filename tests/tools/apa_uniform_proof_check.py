"""Machine checks backing the A Painter Ant uniform-in-n correctness proof.

Run:  uv run python tests/tools/apa_uniform_proof_check.py

Each check corresponds to a lemma in docs/a_painter_ant_uniform_proof.md.
It is a standing check, not a one-time run: a change to the head, body, or
routing invalidates the motif table, and re-running this is how that is
caught.  Named without a ``test_`` prefix so pytest does not collect it --
it takes minutes, and the checked-in tests cover the shipped behaviour.
The proof reduces "all tables at every arity" to a finite computation, in
the style of docs/proofs.md: the arity-dependent part is arithmetic over
signed sums of distinct powers of two (L1, L2), and the behavioural part is
confined to a bounded window whose vocabulary does not grow with n (L3, L4).
"""

from __future__ import annotations

import itertools
import random
import sys
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from esolangs.tools.boolean.a_painter_ant import (
    _bit_is_horizontal,
    _bit_move,
    _instantiate_apa,
    _leaf_color,
    _leaf_positions,
    _reverse_moves,
    a_painter_ant,
)
from tests.tools.a_painter_ant_trace import run

_D = {"n": (0, -1), "s": (0, 1), "e": (1, 0), "w": (-1, 0)}


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


def head_block_lengths(table: str, n: int) -> list[int]:
    """Non-space length of each head leaf-block, in head-visit order."""
    out = []
    for _x, _y, leaf_bits in _leaf_positions(n):
        if not _leaf_color(table, list(leaf_bits)):
            out.append(0)
            continue
        outbound = "WS" if n >= 3 and n % 2 == 1 else ""
        outbound += "".join(
            (
                ("NE" if _bit_is_horizontal(n, k) else "WS") + _bit_move(n, k, b)
                if n >= 2
                else _bit_move(n, k, b)
            )
            for k, b in enumerate(leaf_bits)
        )
        out.append(len(outbound + "P" + _reverse_moves(outbound)))
    return out


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
    """
    prog = _instantiate_apa(a_painter_ant(table), bits_of(idx, n))
    length = len([c for c in prog if not c.isspace()])
    first = run(prog, 1)
    second = run(prog, 2)
    lx, ly = first.position
    steps2 = second.steps[length:]

    pos = 1
    rest_ok = True
    for blen in head_block_lengths(table, n):
        if blen == 0:
            continue
        pos += blen
        if pos - 1 < len(steps2):
            p = steps2[pos - 1].position
            if (p[0] - lx, p[1] - ly) != (0, -1):
                rest_ok = False

    zero_paint = first.grid == second.grid
    fixed = second.position == first.position
    correct = first.landing_colour() == int(table[idx])
    radius = max(max(abs(s.position[0] - lx), abs(s.position[1] - ly)) for s in steps2)
    return rest_ok, zero_paint, fixed, correct, radius


def _unit_spans(n: int, leaf_bits) -> list[tuple[str, object, object, int]]:
    """(kind, horizontal, bit, length) per unit of a leaf block, in order."""
    spans: list[tuple[str, object, object, int]] = []
    lead = "WS" if n >= 3 and n % 2 == 1 else ""
    if lead:
        spans.append(("lead", None, None, len(lead)))
    for k, b in enumerate(leaf_bits):
        horizontal = _bit_is_horizontal(n, k)
        anchor = "NE" if horizontal else "WS"
        spans.append(("out", horizontal, b, len(anchor) + len(_bit_move(n, k, b))))
    spans.append(("P", None, None, 1))
    for k in reversed(range(len(leaf_bits))):
        horizontal = _bit_is_horizontal(n, k)
        anchor = "NE" if horizontal else "WS"
        spans.append(
            (
                "rev",
                horizontal,
                leaf_bits[k],
                len(_bit_move(n, k, leaf_bits[k])) + len(anchor),
            )
        )
    if lead:
        spans.append(("revlead", None, None, len(lead)))
    return spans


def motif_pass(
    table: str, idx: int, n: int, motifs: dict, errors: list, *, learn: bool
):
    """Learn or replay the per-unit motif table for one program's cycle 2."""
    prog = _instantiate_apa(a_painter_ant(table), bits_of(idx, n))
    length = len([c for c in prog if not c.isspace()])
    first = run(prog, 1)
    second = run(prog, 2)
    lx, ly = first.position
    steps2 = second.steps[length:]
    leaf_white = first.grid.get((lx, ly), 0) == 1

    pos = 1
    for _x, _y, leaf_bits in _leaf_positions(n):
        if not _leaf_color(table, list(leaf_bits)):
            continue
        spans = _unit_spans(n, leaf_bits)
        if pos - 1 + sum(s[3] for s in spans) > len(steps2):
            return
        cur = None
        for kind, horizontal, bit, span in spans:
            seg = steps2[pos - 1 : pos - 1 + span]
            pos += span
            entry = (seg[0].position[0] - lx, seg[0].position[1] - ly)
            exit_ = (seg[-1].position[0] - lx, seg[-1].position[1] - ly)
            fired_low = sum(
                1 for s in seg if s.command.islower() and s.action == "moved"
            )
            if cur is None:
                cur = entry
            key = (kind, horizontal, bit, leaf_white, cur)
            if learn:
                if key in motifs and motifs[key] != (exit_, fired_low):
                    errors.append(("conflict", key, n))
                motifs[key] = (exit_, fired_low)
            else:
                got = motifs.get(key)
                if got is None:
                    errors.append(("missing", key, n))
                elif got[0] != exit_:
                    errors.append(("wrong", key, got[0], exit_, n))
                    return
            cur = exit_


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
    for table in tables:
        for idx in range(size):
            motif_pass(table, idx, 5, motifs, errors, learn=True)
    fired = {v[1] for v in motifs.values()}
    entries = {k[4] for k in motifs}
    print(f"  learned {len(motifs)} entries from n=5, conflicts {len(errors)}")
    print(f"  lowercase steps fired inside a unit: {sorted(fired)}")
    print(f"  entry offsets: {sorted(entries)}")
    assert not errors
    assert fired == {0}

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
        step = max(1, size // 8)
        for table in tables:
            for idx in range(0, size, step):
                checked += 1
                motif_pass(table, idx, n, motifs, errors, learn=False)
        print(
            f"  n={n}: {checked} programs replayed, "
            f"prediction errors {len(errors) - before}"
        )
        assert len(errors) == before

    print("\nall lemma checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
