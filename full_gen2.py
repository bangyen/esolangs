"""Full strategy ladder from the READING prologue.

The first prototype ran only two of minifuck()'s three strategies and no
`settle` variation, which is why n=2 came back 0/16.  This mirrors the real
generator's ladder, including _find_parked and the settle re-crossings.

`settle` re-crosses the bit region to advance the affine state; the reading
prologue can do the same by clamping and walking back over its banked cells.
"""
import sys
import importlib
sys.path.insert(0, "src")
M = importlib.import_module("esolangs.tools.boolean.minifuck")

from reading_gen import reading_joint  # noqa: E402


def prepared(n, settle=0):
    j = reading_joint(n)
    for _ in range(settle):
        M._clamp(j)
        M._walk_to(j, M._BASE - 1)
    return j


def build(truth_table, verbose=False):
    n = M._validate_truth_table(truth_table)
    want = tuple(int(c) for c in truth_table)
    frontier = M._BASE + n * M._SPAN + 6

    # 1. the carry chain's own answer
    base = prepared(n)
    M._clamp(base)
    for acc in range(9, frontier):
        hit = M._try_print(base, truth_table, acc)
        if hit is not None:
            return hit.template(), "scan"

    # 2. search for the answer column
    for park in range(M._BASE - 2, M._BASE + 2 * n + 4):
        probe = prepared(n)
        M._clamp(probe)
        try:
            M._walk_to(probe, park)
        except ValueError:
            continue
        found = M._find_column(probe, want, frontier + 8, M._COLUMN_DEPTH)
        if found is None:
            continue
        code, _cell = found
        probe.emit(code)
        M._clamp(probe)
        for acc in range(9, frontier + 8):
            hit = M._try_print(probe, truth_table, acc)
            if hit is not None:
                return hit.template(), "column"

    # 3. park the pointer on the answer as part of the search
    for code, _cell in M._find_parked(
        prepared(n, settle=M._SETTLE),
        want,
        frontier + 8,
        M._PARKED_DEPTH,
        M._PARKED_LIMIT,
    ):
        probe = prepared(n, settle=M._SETTLE)
        probe.emit(code)
        M._clamp(probe)
        for acc in range(9, frontier + 8):
            hit = M._try_print(probe, truth_table, acc)
            if hit is not None:
                return hit.template(), "parked"
    return None, None


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    tables = [format(i, "04b") for i in range(16)] if which == "all" else [which]
    ok = 0
    for t in tables:
        prog, how = build(t)
        if prog:
            ok += 1
        print(f"  {t}: {'OK len=' + str(len(prog)) + ' via ' + how if prog else 'no program'}",
              flush=True)
    print(f"\n{ok}/{len(tables)} tables")
