"""Screen every boolean generator for symmetry and pruning upside at n=3.

The companion of ``screen_input_reorder.py``: each generator builds all 256
three-input tables (and all 16 two-input ones) once, and every column is a
lookup over those sizes.  A percentage is ``100 * (1 - sum(min)/sum(own))``
where ``min`` is the shortest build over the transformed tables:

``outneg``
    The table or its complement -- build ``not f`` and invert the answer.
``inpol``
    Any of the 8 input-polarity flips -- swap an input's 0 and 1 arms.
``npn``
    Any complement, flip and input order together (96 candidates), so the
    excess over the reorder screen is what polarity and negation add.
``ignored``
    For three-input tables with exactly two essential inputs, the mean
    characters over the two-input build of their projection: what reading
    an input the function ignores costs (Line and Piet paid this once).

Every figure is an upper bound.  It charges nothing for the transform --
the inverter a negated build needs, or a polarity flip that a uniform
``(zero, one)`` fill pair forbids (``docs/limitations.md``) -- and the
``ignored`` column includes the read itself, which the interface keeps.
"""

from itertools import permutations
from time import perf_counter

from esolangs.registry import LANGUAGES
from esolangs.tools.helpers import essential_inputs, permute_truth_table, read_at

TABLES = [format(i, "08b") for i in range(256)]
PAIRS = [format(i, "04b") for i in range(16)]
PERMS = list(permutations(range(3)))


def _negate(table: str) -> str:
    return table.translate(str.maketrans("01", "10"))


def _flip(table: str, mask: int) -> str:
    """Return the table with the inputs set in ``mask`` inverted."""
    return "".join(table[row ^ mask] for row in range(len(table)))


def _sizes(gen: object, tables: list[str]) -> dict[str, int | None]:
    """Build every table once; ``None`` marks an arity the generator refuses.

    ``ValueError`` is the refusal; anything else is a real failure and
    propagates.
    """
    assert callable(gen)
    sizes: dict[str, int | None] = {}
    for table in tables:
        try:
            sizes[table] = len(str(gen(table)))
        except ValueError:
            sizes[table] = None
    return sizes


def screen(gen: object) -> tuple[float, float, float, float, float] | None:
    """Return (outneg %, inpol %, npn %, ignored chars, seconds), or None."""
    start = perf_counter()
    sizes = _sizes(gen, TABLES)
    pairs = _sizes(gen, PAIRS)
    elapsed = perf_counter() - start
    built = [t for t in TABLES if sizes[t] is not None]
    if not built:
        return None
    own = sum(sizes[t] or 0 for t in built)

    def upside(candidates: object) -> float:
        assert callable(candidates)
        best = 0
        for table in built:
            found = [s for c in candidates(table) if (s := sizes[c]) is not None]
            best += min(found, default=sizes[table] or 0)
        return 100 * (1 - best / own)

    outneg = upside(lambda t: [t, _negate(t)])
    inpol = upside(lambda t: [_flip(t, mask) for mask in range(8)])
    npn = upside(
        lambda t: [
            _flip(permute_truth_table(u, perm), mask)
            for u in (t, _negate(t))
            for perm in PERMS
            for mask in range(8)
        ]
    )
    extra = []
    for table in built:
        essential = essential_inputs(table, 3)
        if len(essential) == 2:
            projected = pairs[read_at(table, essential, 3)]
            if projected is not None:
                extra.append((sizes[table] or 0) - projected)
    ignored = sum(extra) / len(extra) if extra else float("nan")
    return outneg, inpol, npn, ignored, elapsed


def main() -> None:
    """Screen the registry and print one row per language, best NPN first."""
    rows = []
    for key, lang in sorted(LANGUAGES.items()):
        if lang.boolean is None:
            continue
        result = screen(lang.boolean)
        if result is None:
            continue
        rows.append((key, *result))
    rows.sort(key=lambda row: (-row[3], row[0]))
    print(
        f"{'language':<32}{'outneg%':>8}{'inpol%':>8}{'npn%':>7}"
        f"{'ignored':>9}{'sec':>6}"
    )
    for key, outneg, inpol, npn, ignored, elapsed in rows:
        print(
            f"{key:<32}{outneg:>8.1f}{inpol:>8.1f}{npn:>7.1f}"
            f"{ignored:>9.1f}{elapsed:>6.1f}"
        )


if __name__ == "__main__":
    main()
