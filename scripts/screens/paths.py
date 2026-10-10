"""Screen every generation path for a canonical piece its default applies.

Each path (default, ``width`` 1/8/40, ``balance``, every non-default dialect
choice) builds four table classes; each ratio is against the same path's
build, so a path is compared with itself before it is compared with the
default:

- ``c1``: a random ``n``-input table plus one ignored input (first, middle,
  last), over the ``n``-input build; ``fresh``, a random ``n + 1`` table over
  the same build, is what a real input costs.
- ``c2``: an ``n + 1`` table whose second half is constant, over random.
- ``c3``: an ``n + 1`` table tiled from repeated blocks, over random.

A path is flagged when a ratio exceeds its default's by ``SLACK``; worst of
three tables each.  Round 5 (Oct 2026) found real gaps on 13 generators this
way and ten artifacts: a narrow width's size floor, padding, or ``balance``
trading area for squareness.  Sizes only; a fix still runs every row.  Run
from the repository root: ``python scripts/screens/paths.py [N] [LANG ...]``.
"""

import random
import sys
from pathlib import Path
from typing import Any, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _build import ignore, random_table, source_size, tiled

import esolangs
from esolangs.settings import DialectSettings

#: How far a path's ratio may exceed its default's before it is flagged.
SLACK = 0.25


def _size(name: str, table: str, options: dict[str, Any]) -> int | None:
    """Return characters, or raster area; ``None`` where the path refuses."""
    try:
        program = esolangs.generate(name, table, **options)
    except (ValueError, esolangs.ArgumentError):
        return None
    return source_size(name, program)


def paths(name: str) -> dict[str, dict[str, Any]]:
    """Return every generation path ``name`` offers, keyed by a label."""
    info = esolangs.describe(name)
    found: dict[str, dict[str, Any]] = {"default": {}}
    if info["width_aware"]:
        found |= {f"width={w}": {"width": w} for w in (1, 8, 40)}
    found["balance"] = {"balance": True}
    for key, spec in (info.get("dialect_settings") or {}).items():
        for choice in spec["choices"] or ():
            if choice != spec["default"]:
                found[f"{key}={choice}"] = {
                    "settings": DialectSettings(**{key: choice})
                }
    return found


def ratios(name: str, options: dict[str, Any], n: int) -> list[float] | None:
    """Return worst ``[c1, fresh, c2, c3]`` over three seeded tables."""
    rng = random.Random(2026)
    worst = [0.0] * 4
    for _ in range(3):
        base, fresh = random_table(n, rng), random_table(n + 1, rng)
        ignored = [ignore(base, at) for at in (0, (n + 1) // 2, n)]
        const = random_table(n, rng) + "0" * (1 << n)
        tables = [base, fresh, const, tiled(n + 1, rng), *ignored]
        sizes = [_size(name, table, options) for table in tables]
        if not all(sizes):
            return None
        b, f, c, t, *i = cast("list[int]", sizes)
        found = [max(i) / b, f / b, c / f, t / f]
        worst = [max(w, x) for w, x in zip(worst, found, strict=True)]
    return worst


def main(argv: list[str]) -> int:
    """Print every flagged path with its ratio and its default's."""
    n = int(argv[0]) if argv and argv[0].isdigit() else 5
    names = [a for a in argv if not a.isdigit()] or [
        name
        for name in esolangs.list_languages()
        if esolangs.describe(name)["boolean_generator"]
    ]
    for name in names:
        found = {label: ratios(name, o, n) for label, o in paths(name).items()}
        default = found.pop("default")
        if default is None:
            continue
        for label, got in found.items():
            if got is None:
                continue
            flags = [
                f"{piece} {d:.2f}->{g:.2f}"
                for piece, d, g in zip(
                    ("c1", "", "c2", "c3"), default, got, strict=True
                )
                if piece and g - d > SLACK
            ]
            if flags:
                print(f"{name:<32}{label:<28}{'; '.join(flags)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
