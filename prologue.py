"""A two-input reading prologue: read, bank, re-zero, split -- twice.

Composes the verified pieces:
  READ    "[<."                       one bit, no junk output
  GADGET  "[[[<[[[[[[[[[[[<<<[<[[[<"  re-zero the pool, bank the bit
  SPLIT   "<[<"                       turn the banked bit into a ptr offset

Checks all four 2-bit inputs stay separated, read exactly twice, and emit
nothing.
"""
import sys
sys.path.insert(0, "src")
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based import minifuck

READ = "[<."
GADGET = "[[[<[[[[[[[[[[[<<<[<[[[<"
SPLIT = "<[<"


class CountIO(ScriptedIO):
    def __init__(s, t):
        super().__init__(t)
        s.reads = 0

    def input_char(s, p="Input: "):
        s.reads += 1
        return super().input_char(p)


def state(code, bits):
    io = CountIO("".join(f"{b}\n" for b in bits))
    m = minifuck._Machine(code, io)
    try:
        while not m.halted:
            m.step()
    except EOFError:
        return None
    return io.reads, tuple(m.tape), m.ptr, io.getvalue()


one = READ + GADGET + SPLIT
print("one input:")
for b in "01":
    r = state(one, b)
    print(f"  {b} -> reads={r[0]} ptr={r[2]} out={r[3]!r} c6:14={list(r[1][6:14])}")

two = READ + GADGET + SPLIT + READ + GADGET + SPLIT
print()
print("two inputs:")
seen = {}
for bits in ["00", "01", "10", "11"]:
    r = state(two, bits)
    if r is None:
        print(f"  {bits} -> EOF")
        continue
    print(f"  {bits} -> reads={r[0]} ptr={r[2]} out={r[3]!r} c6:16={list(r[1][6:16])}")
    seen[bits] = (r[1], r[2])

print()
print("  all four states distinct? ", len(set(seen.values())) == len(seen))
print("  reads uniform?           ",
      len({state(two, b)[0] for b in ["00", "01", "10", "11"]}) == 1)
print("  output clean (no junk)?  ",
      all(state(two, b)[3] == "" for b in ["00", "01", "10", "11"]))
