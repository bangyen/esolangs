"""Which piece leaves cell 7 input-dependent at n=2?

Walk the prologue piece by piece and report the pool columns after each,
so the culprit is located rather than guessed.
"""
import sys
import importlib
sys.path.insert(0, "src")
M = importlib.import_module("esolangs.tools.boolean.minifuck")
from reading_gen2 import _ReadSim, _advance  # noqa: E402

READ = "[<."
GADGET = "[[[<[[[[[[[[[[[<<<[<[[[<"
SPLIT = "<[<"

n = 2
rows = [[(r >> (n - 1 - k)) & 1 for k in range(n)] for r in range(2**n)]
sims = [_ReadSim(512, feed=row) for row in rows]

steps = [
    ("read 1", READ, 0),
    ("gadget 1", GADGET, 0),
    ("split 1", SPLIT, 0),
    ("read 2", READ, 1),
    ("gadget 2", GADGET, 1),
    ("split 2", SPLIT, 1),
]

for label, code, idx in steps:
    for sim, row in zip(sims, rows):
        _advance(sim, code, row[idx])
    cols = {c: tuple(s.tape[c] for s in sims) for c in range(8)}
    bad = [c for c, v in cols.items() if len(set(v)) != 1]
    print(f"after {label:9s} ptrs={[s.ptr for s in sims]} "
          f"pool-dependent={bad}")
    if bad:
        for c in bad:
            print(f"      cell {c}: {cols[c]}")

print()
print("cells 8-12 at the end:")
for c in range(8, 13):
    print(f"   cell {c}: {tuple(s.tape[c] for s in sims)}")
