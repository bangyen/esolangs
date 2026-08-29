"""Why does _try_print never succeed from the reading prologue?"""
import sys
import importlib
sys.path.insert(0, "src")
M = importlib.import_module("esolangs.tools.boolean.minifuck")
from reading_gen import reading_joint  # noqa: E402

for n in (1, 2):
    j = reading_joint(n)
    M._clamp(j)
    print(f"n={n}: pool columns after clamp (per cell, one entry per row)")
    for cell in range(8):
        col = j.col(cell)
        flag = "" if len(set(col)) == 1 else "   <-- INPUT-DEPENDENT"
        print(f"   cell {cell}: {col}{flag}")
    print(f"   ptrs: {[m.ptr for m in j.ms]}")
    print()

# Compare with the embed path, which works.
print("embed path, for contrast:")
e = M._embed(2)
M._clamp(e)
for cell in range(8):
    col = e.col(cell)
    flag = "" if len(set(col)) == 1 else "   <-- INPUT-DEPENDENT"
    print(f"   cell {cell}: {col}{flag}")
print(f"   ptrs: {[m.ptr for m in e.ms]}")
