"""Machine checks backing the A Painter Ant uniform-in-n correctness proof."""

from __future__ import annotations

import random
import sys
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from esolangs.tools.a_painter_ant import a_painter_ant
from esolangs.tools.helpers import TEMPLATE_CHAR
from tests.tools.a_painter_ant_trace import run
from tests.tools.fills import fill

_instantiate_apa = fill("A Painter Ant")


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
    """Partial indices stay in the table; the saturated walk lands on ``min``."""
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
    """A zero's walk collapses to nothing; a one's is its exact length."""
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
    """Every motif of passes 1 and 2, the fixed-point verdict, and the answer."""
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
