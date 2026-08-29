"""Can a read-gadget prologue reach the embed's joint state?

The embed encodes bit i partly in the POINTER (n=2: ptr 18 vs 19), which is
what the endgame reads.  The read gadget deliberately keeps the pointer
shared.  Question: from the gadget's banked state, can '[' / '<' alone move
the pointer input-dependently -- i.e. convert a banked cell into a pointer
offset -- the way `_set_bit`'s "[<" does?

Key fact from the interpreter: '[' on a 1-cell clears it and SKIPS the next
instruction; on a 0-cell it flips the neighbour and does not skip.  A skip
diverges STATE but the instruction stream is shared -- so a pointer split
must come from the skip itself.
"""
import sys
sys.path.insert(0, "src")
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based import minifuck

GADGET = "[<." + "[[[<[[[[[[[[[[[<<<[<[[[<"


def state(code, bits):
    io = ScriptedIO("".join(f"{b}\n" for b in bits))
    m = minifuck._Machine(code, io)
    try:
        while not m.halted:
            m.step()
    except EOFError:
        return None
    return list(m.tape), m.ptr, io.getvalue()


# The banked bit sits at cell 8 (and 10). Walk the pointer to just before it,
# then '[' there: on a 1 it clears+skips, on a 0 it flips the neighbour.
# That is exactly `_set_bit`'s mechanism, now driven by a READ bit.
print("gadget end state:")
for b in "01":
    tape, ptr, out = state(GADGET, b)
    print(f"  bit={b} ptr={ptr} cells[6:14]={tape[6:14]} out={out!r}")

print()
print("append '[' at the bank (ptr 8 -> flips cell 9; bank is 8/10):")
for suffix in ["[", "[[", "<[", "[<", "<<[", "[x"]:
    line = []
    for b in "01":
        r = state(GADGET + suffix, b)
        if r is None:
            line.append(f"bit={b} EOF")
            continue
        tape, ptr, out = r
        line.append(f"bit={b} ptr={ptr} c6:14={tape[6:14]}")
    same = state(GADGET + suffix, "0")[1] == state(GADGET + suffix, "1")[1]
    print(f"  {suffix!r:6s} ptr-split={not same}  " + " | ".join(line))
