"""Search for a suffix that turns the banked bit into a POINTER split.

`_set_bit`'s "[<" works because '[' on a 1-cell skips the following '<':
the 1-branch keeps the pointer, the 0-branch steps back.  So a split needs
'[' to land ON a cell that differs between the branches, with a pointer-
moving instruction right after it.

Search over '[' and '<' from the gadget's live state for any suffix where
the two branches end with DIFFERENT pointers -- the encoding the embed and
endgame expect.
"""
import sys
from collections import deque
sys.path.insert(0, "src")
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based import minifuck

GADGET = "[<." + "[[[<[[[[[[[[[[[<<<[<[[[<"


def run(code, bit):
    io = ScriptedIO(f"{bit}\n")
    m = minifuck._Machine(code, io)
    try:
        while not m.halted:
            m.step()
    except EOFError:
        return None
    return tuple(m.tape), m.ptr, io.getvalue()


hits = []
for n in range(1, 13):
    found = False
    # breadth-first over suffixes of length n
    stack = [""]
    for _ in range(n):
        stack = [s + c for s in stack for c in "[<"]
    for suf in stack:
        a = run(GADGET + suf, "0")
        b = run(GADGET + suf, "1")
        if a is None or b is None:
            continue
        if a[2] or b[2]:      # no junk output allowed
            continue
        if a[1] != b[1]:      # pointer split!
            hits.append((suf, a[1], b[1]))
            found = True
    if found:
        print(f"length {n}: {len(hits)} pointer-splitting suffixes")
        for suf, p0, p1 in hits[:6]:
            print(f"   {suf!r}  ptr: bit0={p0} bit1={p1}")
        break
    print(f"length {n}: none", flush=True)
