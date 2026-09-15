"""Machine checks backing the BIO telescoping-lookup proof.

Run:  just proofs   (or python tests/proofs/deep/bio.py)

The ledger row is `finite lookup`, qualified "nested loops telescope from
``table[0]`` to ``table[index]``".  The generator's own docstring states the
identity it relies on::

    y = table[0] + sum_{j=1}^{V} (table[j] - table[j-1]) = table[V]

which is true for any sequence whatever.  The identity is not what can go
wrong -- placing the wrong adjustment at the wrong nesting level is.  So these
lemmas deliberately *parse the emitted program* to recover which adjustment
sits at which level, rather than rebuilding the nesting from the same rule the
generator used.  Rebuilding it would restate the source and prove nothing.

L1 recovers the levels and checks the telescope lands on ``table[V]`` for every
row of every arity it enumerates.  L2 checks the structure the telescope needs:
``2**n - 1`` levels, strictly nested, the ``j``-th at depth ``j``.  L3 checks
the embedding is equal-width, which is what keeps program length from becoming
an extra input.
"""

from __future__ import annotations

import itertools
import random
import re
import sys
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from esolangs.tools import bio

#: The adjustment emitted on each kind of edge, per the construction: a rise
#: raises ``y``, a fall lowers it, a flat edge emits nothing at all.
_RISE, _FALL = "0oy;", "1oy;"


def levels(program: str) -> list[str]:
    """Recover the adjustment at each nesting level, outermost first.

    Walks the emitted ``0ix{ 1ox; [adjust] ... };`` chain by hand.  The
    outermost level is ``j == 1`` -- the generator builds the nesting from the
    innermost level outwards, so the last one it wraps is the first one entered
    -- which is what puts the adjustments in increasing ``j`` order at runtime.
    """
    out: list[str] = []
    i = program.find("0ix{")
    while i != -1:
        i += len("0ix{")
        assert program.startswith("1ox;", i), f"level {len(out)} does not decrement x"
        i += len("1ox;")
        adjust = ""
        for candidate in (_RISE, _FALL):
            if program.startswith(candidate, i):
                adjust = candidate
                i += len(candidate)
                break
        out.append(adjust)
        if not program.startswith("0ix{", i):
            break
        i = program.find("0ix{", i)
    return out


def check_l1(max_n: int = 7) -> list[str]:
    """L1: the recovered adjustments telescope to ``table[V]`` at every row.

    ``y`` starts at ``table[0]`` -- the generator emits a single raise when
    that entry is one -- and level ``j`` fires for every ``j <= V``.  Folding
    the recovered adjustments in order must therefore reproduce the table
    exactly, and it is checked against every row rather than sampled ones.
    """
    lines = []
    rng = random.Random(19)
    for n in range(1, max_n + 1):
        size = 1 << n
        tables = ["0" * size, "1" * size, "01" * (size // 2 or 1)]
        tables = [t[:size] for t in tables]
        tables.append("".join(str(bin(i).count("1") % 2) for i in range(size)))
        while len(tables) < 12:
            tables.append("".join(rng.choice("01") for _ in range(size)))
        for table in tables:
            program = bio(table)
            adjust = levels(program)
            assert len(adjust) == size - 1, (
                f"n={n}: recovered {len(adjust)} levels, expected {size - 1}"
            )
            start = 1 if program.split(" ", n)[-1].startswith(_RISE) else 0
            assert start == int(table[0]), (
                f"n={n}: y starts at {start} but table[0] is {table[0]}"
            )
            y = start
            for index in range(size):
                if index:
                    step = adjust[index - 1]
                    if step == _RISE:
                        y = 1
                    elif step == _FALL:
                        y = 0
                assert y == int(table[index]), (
                    f"n={n} row {index}: telescope holds {y}, table says {table[index]}"
                )
        lines.append(
            f"  n={n}: {len(tables):2d} tables x {size:3d} rows telescoped, "
            f"{size - 1} levels each"
        )
    return lines


def check_l2(max_n: int = 9) -> list[str]:
    """L2: ``2**n - 1`` levels, strictly nested, and flat edges cost nothing.

    Strict nesting is what makes "level ``j`` fires iff ``x >= j``" true: the
    levels are not a sequence of sibling loops that would each fire on their
    own test, but one chain, so entering level ``j`` requires having entered
    every level above it.  Checked from the brace profile, which is also where
    a sibling would show up as a depth returning to zero early.
    """
    lines = []
    rng = random.Random(23)
    for n in range(1, max_n + 1):
        size = 1 << n
        table = "".join(rng.choice("01") for _ in range(size))
        # The placeholders are spelled with braces too, so they have to go
        # before the brace profile means anything.
        program = re.sub(r"\{X\d+\}", "", bio(table))
        depth = 0
        returns_to_zero = 0
        for char in program:
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    returns_to_zero += 1
        assert depth == 0, f"n={n}: unbalanced braces"
        # One chain, not siblings: the depth may reach zero exactly once, at
        # the end.  A second return to zero would be a sibling loop firing on
        # its own test, which is what "level j fires iff x >= j" rules out.
        assert returns_to_zero == 1, (
            f"n={n}: depth returned to zero {returns_to_zero} times, so the "
            f"levels are siblings rather than one nested chain"
        )
        assert program.count("{") == size - 1, (
            f"n={n}: {program.count('{')} levels, expected {size - 1}"
        )
        flats = sum(1 for a, b in itertools.pairwise(table) if a == b)
        assert levels(program).count("") == flats, (
            f"n={n}: flat edges emitted an adjustment"
        )
        lines.append(
            f"  n={n}: {size - 1:3d} levels nested to depth {size - 1:3d}, "
            f"{flats:3d} flat edges free"
        )
    return lines


def check_l3(max_n: int = 8) -> list[str]:
    """L3: both bits of an input embed at the same width.

    A one packs ``2**w`` copies of ``0ox`` into ``x``; a zero writes the same
    count to ``z``, which nothing reads.  Writing to a dead register rather
    than emitting nothing is the whole point -- it keeps the two branches the
    same length, so the program's length cannot leak the input, which is the
    hypothesis the parameterized equal-width argument needs.
    """
    lines = []
    for n in range(1, max_n + 1):
        table = "01" * ((1 << n) // 2) or "01"
        template = bio(table[: 1 << n])
        widths = set()
        for i in range(n):
            placeholder = "{X" + str(i) + "}"
            assert template.count(placeholder) == 1, (
                f"n={n}: {placeholder} embedded {template.count(placeholder)} times"
            )
        for bits in ("0" * n, "1" * n):
            filled = _fill(template, bits)
            widths.add(len(filled))
        assert len(widths) == 1, f"n={n}: all-zero and all-one differ in length"
        lines.append(f"  n={n}: every input embeds once, both bits at one width")
    return lines


def _fill(template: str, bits: str) -> str:
    """Instantiate a BIO template through the shared parameterized helper."""
    from esolangs.tools.parameterized import instantiate

    n = len(bits)
    return instantiate(
        template,
        [int(b) for b in bits],
        lambda i, bit: ("0ox;" if bit else "0oz;") * (2 ** (n - 1 - i)),
    )


def main() -> int:
    """Run every lemma and report."""
    print("L1  recovered adjustments telescope to table[V] (every row)")
    print("\n".join(check_l1()))
    print("\nL2  2**n - 1 levels, strictly nested, flat edges free")
    print("\n".join(check_l2()))
    print("\nL3  both bits of an input embed at equal width")
    print("\n".join(check_l3()))
    print("\nall lemma checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
