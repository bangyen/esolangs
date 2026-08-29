"""Prototype: drive the existing tree/endgame from a READING prologue.

The whole pipeline in tools/boolean/minifuck.py is parameterized on the
_Joint that _embed(n) returns.  If a _Joint can be advanced by a prologue
that READS its bits instead of embedding them, every downstream stage
(_clamp, _try_print, _find_column, _find_parked) should work unchanged.

_Sim marks a '.' on a zero pool as `dead` (it reads).  For a reading
generator that transition is exactly what we want, so this uses a subclass
that performs the read instead of dying.
"""
import sys
sys.path.insert(0, "src")
import importlib
M = importlib.import_module('esolangs.tools.boolean.minifuck')

READ = "[<."
GADGET = "[[[<[[[[[[[[[[[<<<[<[[[<"
SPLIT = "<[<"
PROLOGUE = READ + GADGET + SPLIT


class _ReadSim(M._Sim):
    """A _Sim whose '.' on a zero pool consumes a scripted input bit."""

    __slots__ = ("feed",)

    def __init__(self, size, feed=()):
        super().__init__(size)
        self.feed = list(feed)

    def copy(self):
        clone = _ReadSim.__new__(_ReadSim)
        clone.tape = list(self.tape)
        clone.ptr = self.ptr
        clone.out = list(self.out)
        clone.dead = self.dead
        clone.skip = self.skip
        clone.feed = list(self.feed)
        return clone


def reading_joint(n, size=512):
    """A _Joint whose rows are advanced by the reading prologue."""
    j = M._Joint(n, size=size)
    j.ms = [_ReadSim(size, feed=row) for row in j.rows]
    # Emit the prologue once per input, letting each row consume its own bit.
    for i in range(n):
        for sim, row in zip(j.ms, j.rows):
            _advance(sim, PROLOGUE, row[i])
        j.parts.append(PROLOGUE)
    return j


def _advance(sim, code, bit):
    """Run `code` on `sim`, servicing a read with `bit` (ASCII '0'/'1')."""
    for ch in code:
        if sim.skip:
            sim.skip = False
            continue
        if ch == "<":
            if sim.ptr:
                sim.ptr -= 1
            continue
        sim.ptr += 1
        if sim.ptr + 1 >= len(sim.tape):
            sim.tape.append(0)
        sim.tape[sim.ptr] ^= 1
        if ch == ".":
            pool = int("".join(str(b) for b in sim.tape[:8]), 2)
            if pool:
                sim.out.append(chr(pool))
            else:
                val = format(ord("0") + bit, "08b")
                sim.tape[:8] = [int(c) for c in val]
        elif not sim.tape[sim.ptr]:
            sim.tape[sim.ptr + 1] ^= 1
            sim.skip = True


for n in (1, 2):
    j = reading_joint(n)
    print(f"n={n} prologue len={len(''.join(j.parts))}")
    for row, m in zip(j.rows, j.ms):
        print(f"   row {row} ptr={m.ptr} out={''.join(m.out)!r} c6:18={m.tape[6:18]}")
    states = {(tuple(m.tape), m.ptr) for m in j.ms}
    print(f"   distinct states: {len(states)} of {len(j.ms)}")
    print()
