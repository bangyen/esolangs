"""Drive the existing search+endgame from the READING prologue.

Mirrors minifuck()'s own strategy ladder, but starting from reading_joint(n)
instead of _embed(n).  If a table comes out, the program computes it from
real stdin with clean "0"/"1" output.
"""
import sys
import importlib
sys.path.insert(0, "src")
M = importlib.import_module("esolangs.tools.boolean.minifuck")

from reading_gen import reading_joint, PROLOGUE  # noqa: E402


def build(truth_table):
    n = M._validate_truth_table(truth_table)
    want = tuple(int(c) for c in truth_table)
    frontier = M._BASE + n * M._SPAN + 6

    base = reading_joint(n)
    M._clamp(base)
    for acc in range(9, frontier):
        hit = M._try_print(base, truth_table, acc)
        if hit is not None:
            return hit.template()

    for park in range(M._BASE - 2, M._BASE + 2 * n + 4):
        probe = reading_joint(n)
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
                return hit.template()
    return None


TABLES_1 = ["01", "10", "00", "11"]
TABLES_2 = [format(i, "04b") for i in range(16)]

print("n=1:")
for t in TABLES_1:
    prog = build(t)
    print(f"  {t}: {'OK len=' + str(len(prog)) if prog else 'no program'}")

print()
print("n=2:")
ok = 0
for t in TABLES_2:
    prog = build(t)
    if prog:
        ok += 1
    print(f"  {t}: {'OK len=' + str(len(prog)) if prog else 'no program'}")
print(f"\n{ok}/16 two-input tables")
