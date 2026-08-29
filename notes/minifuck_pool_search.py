"""Widen the pool search beyond clamped `[x` runs.

`pool_fix` only ever tries runs of `[x` separated by clamps, which cannot
reach `0011000|0` for the prototype embed.  The pool is input-independent, so
the honest question is what the *whole* instruction set reaches: search over
`<[x` directly, accepting any state whose cells 0..7 match the target and
whose pointer can still walk out to where the endgame needs it.
"""

import pathlib
import sys
from collections import deque

sys.path.insert(0, str(pathlib.Path(__file__).parent))

import minifuck_boolean_prototype as gen

TARGETS = {
    "0011000|1": (0, 0, 1, 1, 0, 0, 0, 1),
    "0011000|0": (0, 0, 1, 1, 0, 0, 0, 0),
}


def proto_embed(n=2, stride=4, base=16):
    """Build the prototype's own embed, whose pool is the constrained one."""
    j = gen.Joint(n)
    gen.walk_to(j, base - 1)
    for i in range(n):
        j.emit_setter(i)
        j.emit("[x")
        if i + 1 < n:
            j.emit("[x" * (stride - 1))
    return j


def search_pool(j, target, walk_out, maxlen=16):
    """Find code leaving cells 0..7 at `target`, pointer parked at `walk_out`.

    Unlike `pool_fix` this searches the instruction set rather than a fixed
    walk-and-clamp shape, and it requires the pool to be input-independent.
    """
    root = tuple(m.copy() for m in j.ms)
    seen = {tuple(m.key() for m in root)}
    q = deque([(root, "")])
    while q:
        states, prog = q.popleft()
        if len(prog) >= maxlen:
            continue
        for ch in "<[x":
            new = []
            for m in states:
                c = m.copy()
                c.exec(ch)
                new.append(c)
            if any(m.dead for m in new):
                continue
            k = tuple(m.key() for m in new)
            if k in seen:
                continue
            seen.add(k)
            p = prog + ch
            if not any(m.skip for m in new) and len({m.ptr for m in new}) == 1:
                # The pool must read `target` *after* walking out to the
                # endgame's cell, so test the walked-out state, not this one.
                probe = [m.copy() for m in new]
                steps = walk_out - probe[0].ptr
                if steps >= 0:
                    for _ in range(steps):
                        for c2 in "[x":
                            for m in probe:
                                m.exec(c2)
                if steps >= 0 and all(
                    len({m.tape[c] for m in probe}) == 1
                    and probe[0].tape[c] == target[c]
                    for c in range(8)
                ):
                    return p
            q.append((tuple(new), p))
    return None


if __name__ == "__main__":
    import time

    for name, target in TARGETS.items():
        for depth in (12, 16, 20):
            j = proto_embed()
            gen.clamp(j)
            t0 = time.time()
            hit = search_pool(j, target, 19, maxlen=depth)
            print(f"{name} depth<={depth}: {hit!r}  ({time.time() - t0:.0f}s)")
            if hit:
                break
