"""Reading prologue that leaves the POOL CLEAN.

The first version banked each bit but left the final read's ASCII residue in
the pool: at n=2 cell 7 held the second bit, so _endgame rejected every
accumulator with "pool cell 7 is input-dependent".

Fix: run the re-zero GADGET after EVERY read, including the last one, so the
pool ends input-independent while each bit lives on as a pointer offset.
"""
import sys
import importlib
sys.path.insert(0, "src")
M = importlib.import_module("esolangs.tools.boolean.minifuck")

READ = "[<."
GADGET = "[[[<[[[[[[[[[[[<<<[<[[[<"
SPLIT = "<[<"


class _ReadSim(M._Sim):
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


def _advance(sim, code, bit):
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


def reading_joint(n, size=512, unit=READ + GADGET + SPLIT):
    j = M._Joint(n, size=size)
    j.ms = [_ReadSim(size, feed=row) for row in j.rows]
    for i in range(n):
        for sim, row in zip(j.ms, j.rows):
            _advance(sim, unit, row[i])
        j.parts.append(unit)
    return j


if __name__ == "__main__":
    for n in (1, 2, 3):
        j = reading_joint(n)
        M._clamp(j)
        bad = [c for c in range(8) if len(set(j.col(c))) != 1]
        states = {(tuple(m.tape), m.ptr) for m in j.ms}
        outs = {"".join(m.out) for m in j.ms}
        print(f"n={n}: pool-dependent cells={bad} distinct={len(states)}/{len(j.ms)} "
              f"outputs={outs}")
