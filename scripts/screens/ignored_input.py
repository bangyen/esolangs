"""Screen every boolean generator for what an input the table never reads costs.

A random ``n``-input table gains one input it ignores, placed first, in the
middle or last; the figure is the program's growth over the ``n``-input
build.  ``fresh`` is the growth to a random ``(n + 1)``-input table, the
honest cost of one more input: an ignored input that grows a program as
much as ``fresh`` is being built as if it mattered.  ``DOUBLES`` marks a
worst growth above 1.5, maxed over ``n`` in 4..6 and three tables each.

Sizes only.  A fix goes through ``candidate.py``, which runs every row.
Run from the repository root: ``python scripts/screens/ignored_input.py
[LANG ...]``.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _build import chosen, ignore, random_table, sizes

#: Growth above which an ignored input is built as if it mattered.
DOUBLES = 1.5


def main(argv: list[str] | None = None) -> int:
    """Print each generator's worst growth per position."""
    names = sys.argv[1:] if argv is None else argv
    rng = random.Random(2026)
    print(f"{'generator':<28} first  mid   last  fresh")
    for name, gen in chosen(names):
        worst = {"first": 0.0, "mid": 0.0, "last": 0.0, "fresh": 0.0}
        for n in (4, 5, 6):
            for _ in range(3):
                table = random_table(n, rng)
                variants = {
                    "first": ignore(table, 0),
                    "mid": ignore(table, (n + 1) // 2),
                    "last": ignore(table, n),
                    "fresh": random_table(n + 1, rng),
                }
                built = sizes(gen, [table, *variants.values()])
                base = built[table]
                if base is None:
                    continue
                for key, variant in variants.items():
                    size = built[variant]
                    if size is not None:
                        worst[key] = max(worst[key], size / base)
        flag = (
            "DOUBLES"
            if max(worst["first"], worst["mid"], worst["last"]) > DOUBLES
            else ""
        )
        print(
            f"{name:<28} {worst['first']:.2f}  {worst['mid']:.2f}  {worst['last']:.2f}"
            f"  {worst['fresh']:.2f}  {flag}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
