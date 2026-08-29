"""Where does the time actually go? Time each stage separately, with caps."""
import time
import sys
import importlib
sys.path.insert(0, "src")
M = importlib.import_module("esolangs.tools.boolean.minifuck")
from reading_gen import reading_joint  # noqa: E402

n = 2
want = tuple(int(c) for c in "0001")
frontier = M._BASE + n * M._SPAN + 6

t = time.time()
j = reading_joint(n)
print(f"build reading_joint: {time.time() - t:.2f}s", flush=True)

t = time.time()
M._clamp(j)
print(f"clamp:              {time.time() - t:.2f}s", flush=True)

t = time.time()
hits = 0
for acc in range(9, frontier):
    if M._try_print(j, "0001", acc) is not None:
        hits += 1
print(f"scan ({frontier - 9} accs): {time.time() - t:.2f}s, hits={hits}", flush=True)

# One _find_column call, to price the exponential stage.
probe = reading_joint(n)
M._clamp(probe)
M._walk_to(probe, M._BASE)
t = time.time()
found = M._find_column(probe, want, frontier + 8, M._COLUMN_DEPTH)
print(f"_find_column depth={M._COLUMN_DEPTH}: {time.time() - t:.2f}s, found={found is not None}",
      flush=True)
print(f"  (the ladder calls this {M._BASE + 2 * n + 4 - (M._BASE - 2)} times, x2 seps)")
