r"""Whole-template evaluation, so ``3`` can be part of a candidate program.

The affine construction emits code against a running simulation, appending
one character at a time.  That cannot accommodate ``3``: its jump target is
the nearest preceding or following ``3`` *in the finished program*, so
adding a ``3`` retroactively changes what every other ``3`` does.

So a ``3``-bearing candidate has to be built whole and then run whole.  This
module evaluates a complete template by instantiating it once per row and
running each instantiation through the shipped interpreter -- slower per
candidate than the incremental search, but it is the only way the jump
semantics come out right.
"""

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine

# Two characters each, so no instantiation leaks its inputs through len().
ONE = "12"
ZERO = "21"


def instantiate(template, bits):
    """Replace each ``{Xi}`` with the setter for that row's bit."""
    out = template
    for i, bit in enumerate(bits):
        out = out.replace("{X" + str(i) + "}", ONE if bit else ZERO)
    return out


def run(code, limit=20000):
    """Run one instantiation; return (output, status).

    Status is ``halt``, ``loop`` (fuel exhausted) or ``read`` (the program
    tried to consume stdin, which a parameterized program must never do).
    """
    io = ScriptedIO("")
    machine = _Machine(code, io)
    steps = 0
    try:
        while not machine.halted and steps < limit:
            machine.step()
            steps += 1
    except EOFError:
        return io.getvalue(), "read"
    return io.getvalue(), "halt" if machine.halted else "loop"


def table_of(template, n=2, limit=20000):
    """Return the printed digit per row, or None if any row misbehaves.

    Every row must halt cleanly having printed exactly one character, and
    that character must be ``'0'`` or ``'1'``.
    """
    rows = []
    for r in range(2**n):
        bits = [(r >> (n - 1 - k)) & 1 for k in range(n)]
        out, status = run(instantiate(template, bits), limit)
        if status != "halt" or len(out) != 1 or out not in "01":
            return None
        rows.append(out)
    return tuple(rows)


def lengths_equal(template, n=2):
    """Whether every instantiation is the same length."""
    sizes = set()
    for r in range(2**n):
        bits = [(r >> (n - 1 - k)) & 1 for k in range(n)]
        sizes.add(len(instantiate(template, bits)))
    return len(sizes) == 1
