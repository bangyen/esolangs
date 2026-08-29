"""Joint lockstep BFS for a read -> bank -> re-zero gadget.

Start from the two real post-read states (pool 00110000 / 00110001, ptr 1).
Both branches execute the SAME instruction stream -- '[' skips diverge state,
never the stream -- so a pair search cannot produce an unrunnable path the way
a single-state BFS did.

Alphabet is '[' and '<' only: any '.' on a nonzero pool prints a junk byte,
and the contract demands the program's entire output be one clean ASCII digit.

Target: both pools all-zero (so a following '.' READS rather than prints),
ptrs equal (instruction stream stays shared), and some cell >= 8 differing
between the two branches (the bit is banked out of the pool's way).
"""
import sys
from collections import deque

WIDTH = 24  # cells tracked; plenty for a gadget this size


def step(tape, ptr, ins):
    """One interpreter step, mirroring tape_based/minifuck.py exactly."""
    t = list(tape)
    if ins == "<":
        return tuple(t), (ptr - 1 if ptr else ptr), False
    ptr += 1
    while ptr + 1 >= len(t):
        t.append(0)
    t[ptr] ^= 1
    if ins == "[":
        if not t[ptr]:
            t[ptr + 1] ^= 1
            return tuple(t), ptr, True  # skip next instruction
    return tuple(t), ptr, False


def ascii_state(bit):
    """Tape right after a read of ASCII '0'/'1', per the interpreter."""
    val = format(ord("0") + bit, "08b")
    tape = [int(c) for c in val] + [0] * (WIDTH - 8)
    return tuple(tape), 1


def search(max_depth=22):
    s0 = ascii_state(0)
    s1 = ascii_state(1)
    start = (s0[0], s0[1], s1[0], s1[1], False, False)
    seen = {start}
    dq = deque([(start, "")])
    while dq:
        (t0, p0, t1, p1, sk0, sk1), path = dq.popleft()
        if len(path) >= max_depth:
            continue
        for ins in "[<":
            # a pending skip consumes this instruction in that branch
            if sk0:
                n0, q0, s0n = t0, p0, False
            else:
                n0, q0, s0n = step(t0, p0, ins)
            if sk1:
                n1, q1, s1n = t1, p1, False
            else:
                n1, q1, s1n = step(t1, p1, ins)
            newpath = path + ins
            pool0 = any(n0[:8])
            pool1 = any(n1[:8])
            if (not pool0 and not pool1 and q0 == q1
                    and not s0n and not s1n
                    and n0[8:] != n1[8:]):
                return newpath, (n0, q0), (n1, q1)
            key = (n0, q0, n1, q1, s0n, s1n)
            if key not in seen:
                seen.add(key)
                dq.append((key, newpath))
    return None, None, None


path, a, b = search()
print("gadget found:", repr(path))
if path:
    print("  bit=0 -> pool", a[0][:8], "cells8+", a[0][8:14], "ptr", a[1])
    print("  bit=1 -> pool", b[0][:8], "cells8+", b[0][8:14], "ptr", b[1])
