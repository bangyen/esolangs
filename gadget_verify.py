"""Verify the read->bank->re-zero gadget on the SHIPPED interpreter.

The BFS ran a mirror of the step function; this runs the real thing.
Checks, in order:
  1. after read 1 + gadget, the pool is all-zero (so the next '.' READS)
  2. some cell >= 8 differs by the bit (the bit is banked)
  3. the pointer is identical for both bits (instruction stream stays shared)
  4. the NEXT '.' actually reads for both bits, and does not wipe the bank
     (its pre-flip hits ptr+1 -- must not be the banked cell)
"""
import sys
sys.path.insert(0, "src")
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based import minifuck

GADGET = "[[[<[[[[[[[[[[[<<<[<[[[<"
READ = "[<."


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
    return io.reads, list(m.tape), m.ptr, io.getvalue()


print("after READ + GADGET:")
res = {}
for bit in "01":
    r = state(READ + GADGET, bit)
    res[bit] = r
    reads, tape, ptr, out = r
    print(f"  bit={bit} reads={reads} pool={tape[:8]} cells8+={tape[8:20]} ptr={ptr} out={out!r}")

t0, t1 = res["0"][1], res["1"][1]
print()
print("  pool zero for both? ", not any(t0[:8]) and not any(t1[:8]))
print("  ptr equal?          ", res["0"][2] == res["1"][2])
print("  banked (cells>=8 differ)?", t0[8:] != t1[8:])
print("  junk output?        ", repr(res['0'][3]), repr(res['1'][3]))
diff = [i for i in range(8, max(len(t0), len(t1)))
        if (t0[i] if i < len(t0) else 0) != (t1[i] if i < len(t1) else 0)]
print("  differing cells:    ", diff)
print("  ptr+1 (next '.' pre-flip target):", res["0"][2] + 1)
print("  -> pre-flip would clobber bank?  ", (res["0"][2] + 1) in diff)

print()
print("READ + GADGET + second READ:")
for bits in ["00", "01", "10", "11"]:
    r = state(READ + GADGET + READ, bits)
    if r is None:
        print(f"  {bits} -> EOF (second read did not fire)")
        continue
    reads, tape, ptr, out = r
    print(f"  {bits} reads={reads} pool={tape[:8]} cells8+={tape[8:20]} out={out!r}")
