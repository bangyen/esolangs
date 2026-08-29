import sys
import time
import importlib
sys.path.insert(0, "src")
M = importlib.import_module("esolangs.tools.boolean.minifuck")
from reading_gen3 import reading_joint  # noqa: E402


def build(truth_table):
    n = M._validate_truth_table(truth_table)
    want = tuple(int(c) for c in truth_table)
    frontier = M._BASE + n * M._SPAN + 6

    base = reading_joint(n)
    M._clamp(base)
    for acc in range(9, frontier):
        hit = M._try_print(base, truth_table, acc)
        if hit is not None:
            return hit.template(), "scan"

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
                return hit.template(), "column"
    return None, None


if __name__ == "__main__":
    tables = sys.argv[1:] or ["0001"]
    for t in tables:
        t0 = time.time()
        prog, how = build(t)
        dt = time.time() - t0
        label = f"OK len={len(prog)} via {how}" if prog else "no program"
        print(f"RESULT {t}: {label}  {dt:.1f}s", flush=True)
