"""Shared 123 runner for the wall re-check.

The runtime wall in ``docs/walls.md`` rested on two mechanisms that a direct
trace refutes or narrows:

* "the read result is corrupted en route" -- false.  The MSB flip at location
  0 has *parity*: the ``-4 -> 0`` wrap lets the pointer lap, and an even
  number of leftward departures from 0 restores the bit.  ``111211111121``
  echoes its input byte exactly.
* "a TRUE ``3`` re-reads stdin and desyncs every later read" -- narrower than
  stated.  A TRUE ``3`` re-runs only back to the *previous* ``3``, so a read
  before that ``3`` is never re-executed.

So the search below allows lapping reads and segments fenced by ``3``.
"""

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine

# The two bit encodings a boolean program could use for its answer.
ASCII_BITS = ("0", "1")


def run(code, inp="", limit=20000):
    """Run ``code`` on ``inp``.

    Returns ``(output, status)`` where status is one of ``"halt"``,
    ``"loop"`` (fuel exhausted) or ``"eof"`` (ran out of input).
    """
    io = ScriptedIO(inp)
    machine = _Machine(code, io)
    steps = 0
    try:
        while not machine.halted and steps < limit:
            machine.step()
            steps += 1
    except Exception:
        return io.getvalue(), "eof"
    if not machine.halted:
        return io.getvalue(), "loop"
    return io.getvalue(), "halt"


def table_of(code, encoding=ASCII_BITS, limit=20000):
    """Return the 4-entry truth table ``code`` computes, or None.

    The contract mirrors the %^2^-1 one: for each of the four input
    combinations the program reads two bit characters and prints exactly one
    character, which must itself be a bit character.  Anything else (a loop,
    an EOF, a wrong-length output, a non-bit character) disqualifies.
    """
    out = []
    for b0 in (0, 1):
        for b1 in (0, 1):
            text, status = run(code, encoding[b0] + encoding[b1], limit)
            if status != "halt" or len(text) != 1 or text not in encoding:
                return None
            out.append(encoding.index(text))
    return tuple(out)


# The six tables the wall section names as unreached, keyed by name.
TARGETS = {
    "AND": (0, 0, 0, 1),
    "OR": (0, 1, 1, 1),
    "XOR": (0, 1, 1, 0),
    "NAND": (1, 1, 1, 0),
    "NOR": (1, 0, 0, 0),
    "XNOR": (1, 0, 0, 1),
}


def depends_on_both(table):
    """Whether a table genuinely uses both inputs."""
    ignores_first = table[0] == table[2] and table[1] == table[3]
    ignores_second = table[0] == table[1] and table[2] == table[3]
    return not (ignores_first or ignores_second)
