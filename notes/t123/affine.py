r"""Construct the affine tables directly, rather than searching for them.

Flipping is XOR, so with the displacement-neutral setter every cell ends as
a fixed XOR of the input bits.  Byte 48 (``'0'``) and 49 (``'1'``) differ
only in location 7, so a table whose entry is an XOR of a subset of the
inputs (or its complement) should be constructible without any search:

* walk right to location 7 and embed there.  ``12`` flips location 7 -- the
  parity bit of the answer -- while ``21`` flips location 8, which
  ``byte()`` never reads, so a zero-bit contributes nothing;
* the walk home from 7 to -2 passes locations 7..0 flipping each exactly
  once, so whatever the cells hold beforehand is complemented;
* a ``2`` at -2 prints the byte, and a trailing ``1`` steps below zero so
  the program halts.

The pre-pass therefore has to leave locations 0-7 holding
``target XOR 0xFF`` for the ``'0'`` case, adjusted by the embed's own flips.
Everything here is checked against the shipped interpreter, not argued.
"""

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine


def run(code, limit=100000):
    """Run a parameterized instantiation; return (output, halted).

    A parameterized program must never read, so an ``EOFError`` means the
    walk reached location -3 and the candidate is rejected rather than
    crashing the caller.
    """
    io = ScriptedIO("")
    machine = _Machine(code, io)
    steps = 0
    try:
        while not machine.halted and steps < limit:
            machine.step()
            steps += 1
    except EOFError:
        return None, False
    return io.getvalue(), machine.halted


def instantiate(template, bits):
    """Replace each ``{Xi}`` with ``12`` for a one and ``21`` for a zero."""
    out = template
    for i, bit in enumerate(bits):
        out = out.replace("{X" + str(i) + "}", "12" if bit else "21")
    return out


def table_of(template, n=2):
    """Return the printed character per row, or None if a row misbehaves."""
    rows = []
    for r in range(2**n):
        bits = [(r >> (n - 1 - k)) & 1 for k in range(n)]
        code = instantiate(template, bits)
        out, halted = run(code)
        if not halted or len(out) != 1:
            return None
        rows.append(out)
    return tuple(rows)


def main():
    """Probe the walk-home construction and report what it prints.

    From location ``p``, ``k`` ones step to ``p - k`` (wrapping -4 to 0), so
    landing exactly on the write position -2 from ``p`` takes ``p + 2``
    ones.  Each of those steps flips the cell it leaves, so locations
    ``p`` down to ``-1`` are complemented on the way.
    """
    print("--- walk from location p straight to the write position ---")
    for p in range(2, 10):
        code = "2" * p + "1" * (p + 2) + "2" + "1"
        out, halted = run(code)
        shown = repr(out) if out is not None else "READ (rejected)"
        print(f"  p={p}: {code!r:28} -> {shown} halted={halted}")


if __name__ == "__main__":
    main()
