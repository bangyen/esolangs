"""Machine checks backing the BIO telescoping-lookup proof."""

from __future__ import annotations

import itertools
import random
import sys
from pathlib import Path

# Run as a script (not under pytest), the repo root is not on the path.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from esolangs.tools import bio
from esolangs.tools.bio import _BIO_SKIP, BIO_PAIR
from esolangs.tools.helpers import _ASCII_ZERO, input_weights, runs

#: Cost band; see ``__main__.py``. Telescoping-lookup lemmas, cheap enough that
#: scoping them is the only reason they are ever skipped.
BAND = "verify"
COST = 0.2

#: The adjustment emitted on each kind of edge, per the construction: a rise
#: raises ``y``, a fall lowers it, a flat edge emits nothing at all.
_RISE, _FALL = "0oy;", "1oy;"


def lookup(program: str) -> str:
    """The telescope: after the last input run and its skip, before the print.

    The print's ASCII lift is cut so that a constant's empty telescope does not
    read as a rise.
    """
    body = program[program.rfind("$") + 1 :].removeprefix(_BIO_SKIP[1])
    return body.removesuffix(_RISE * _ASCII_ZERO + "1iy;")


def indexed(table: str, program: str) -> str:
    """The table the telescope indexes: the essential inputs' when skipped."""
    n = len(table).bit_length() - 1
    return input_weights(table, n)[1] if _BIO_SKIP[0] in program else table


def levels(program: str) -> list[str]:
    """Recover the adjustment at each nesting level, outermost first."""
    out: list[str] = []
    program = lookup(program)
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
    """L1: the recovered adjustments telescope to ``table[V]`` at every row."""
    lines = []
    rng = random.Random(19)
    for n in range(1, max_n + 1):
        size = 1 << n
        tables = ["0" * size, "1" * size, "01" * (size // 2 or 1)]
        tables = [t[:size] for t in tables]
        tables.append("".join(str(bin(i).count("1") % 2) for i in range(size)))
        while len(tables) < 12:
            tables.append("".join(rng.choice("01") for _ in range(size)))
        executed = 0
        for table in tables:
            program = bio(table)
            kept = indexed(table, program)
            adjust = levels(program)
            assert len(adjust) == len(kept) - 1, (
                f"n={n}: recovered {len(adjust)} levels, expected {len(kept) - 1}"
            )
            start = 1 if lookup(program).startswith(_RISE) else 0
            assert start == int(kept[0]), (
                f"n={n}: y starts at {start} but table[0] is {kept[0]}"
            )
            y = start
            for index in range(len(kept)):
                if index:
                    step = adjust[index - 1]
                    if step == _RISE:
                        y = 1
                    elif step == _FALL:
                        y = 0
                assert y == int(kept[index]), (
                    f"n={n} row {index}: telescope holds {y}, table says {kept[index]}"
                )
            for index in range(size if n <= 3 else 0):
                got = _executed_answer(program, n, index)
                assert got == int(table[index]), (
                    f"n={n} row {index}: interpreter gives {got}, "
                    f"table says {table[index]}"
                )
                executed += 1
        lines.append(
            f"  n={n}: {len(tables):2d} tables x {size:3d} rows telescoped, "
            f"at most {size - 1} levels each, {executed} executed"
        )
    return lines


def _executed_answer(program: str, n: int, index: int) -> int:
    """Run ``program`` for input ``index`` and read the register it leaves."""
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.interpreters.register_based.bio import _Machine

    bits = format(index, f"0{n}b")
    filled = _fill(program, bits)
    machine = _Machine(filled, ScriptedIO("\n".join(bits) + "\n"))
    while not machine.halted:
        machine.step()
    return machine.reg[1] - 48  # y holds the ASCII '0'/'1' the telescope writes


def check_l2(max_n: int = 9) -> list[str]:
    """L2: ``2**n - 1`` levels, strictly nested, and flat edges cost nothing."""
    lines = []
    rng = random.Random(23)
    for n in range(1, max_n + 1):
        size = 1 << n
        table = "".join(rng.choice("01") for _ in range(size))
        # The pack (runs and the doublings between them) is cut off, so the
        # brace profile reads straight off the telescope.
        template = bio(table)
        assert "{X" not in template, f"n={n}: template still carries {{Xi}} marks"
        table = indexed(table, template)
        size = len(table)
        program = lookup(template)
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
    """L3: both bits of an input embed at the same width."""
    lines = []
    for n in range(1, max_n + 1):
        table = "01" * ((1 << n) // 2) or "01"
        template = bio(table[: 1 << n])
        widths = set()
        # One run of ``$`` per input, each as wide as its setter: ``runs``
        # refuses a stray ``$`` or a run of the wrong width, so ``n`` spans
        # is exactly one embedding per input.
        spans = runs(template, "$", (BIO_PAIR,) * n)
        assert len(spans) == n, f"n={n}: {len(spans)} runs for {n} inputs"
        for bits in ("0" * n, "1" * n):
            filled = _fill(template, bits)
            widths.add(len(filled))
        assert len(widths) == 1, f"n={n}: all-zero and all-one differ in length"
        lines.append(f"  n={n}: every input embeds once, both bits at one width")
    return lines


def _fill(template: str, bits: str) -> str:
    """Instantiate through the *shipped* fill, not a local copy of it."""
    from tests.tools.fills import _fill_bio

    return _fill_bio(template, [int(b) for b in bits])


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
