"""The trit gadget machine: the smallest model expressing the digits gadget.

State is an accumulator ``A`` and three cells, every value a single trit
(0..2): the Malbolge digit gadget's behaviour at trit 0, the resolution
the repo's own minimality test (``test_gadget_suffix.py``) uses.  A
program is a tuple of tokens; its cost is its token count.

Tokens:

- ``/`` -- read: ``A`` becomes the next input bit (0 or 1).
- ``Kd`` -- constant: ``A`` becomes ``d``.
- ``d`` -- apply: ``A`` and cell ``d`` both become ``crazy0(A, cell d)``,
  Malbolge's ``p`` over that cell at trit 0.

``crazy0(a, c)`` is the low trit of the interpreter's ``_crazy(a, c)``
for single-trit arguments; a test pins this table against the
interpreter, and pins the shipped gadget's closed form against
:func:`run`, so the model cannot drift from the repo's.
"""

from __future__ import annotations

#: crazy at trit 0: ``CRAZY0[a][c]``.
CRAZY0: tuple[tuple[int, int, int], ...] = ((1, 1, 2), (0, 0, 2), (0, 2, 1))

#: Every token, in search order: read, cell applies, constants.
FULL_ALPHABET: tuple[str, ...] = ("/", "0", "1", "2", "K0", "K1", "K2")
#: The suffix alphabet: no reads (a prefix has already consumed them).
SUFFIX_ALPHABET: tuple[str, ...] = ("0", "1", "2", "K0", "K1", "K2")

#: A machine state: ``(A, cells)``.
type State = tuple[int, tuple[int, int, int]]

#: The zeroed start state.
ZERO: State = (0, (0, 0, 0))


def step(state: State, op: str, bit: int | None = None) -> State:
    """Return the state after one token; ``bit`` is consumed by ``/``."""
    a, cells = state
    if op == "/":
        if bit is None:
            raise ValueError("read with no input bit left")
        return bit, cells
    if op.startswith("K"):
        return int(op[1]), cells
    i = int(op)
    a = CRAZY0[a][cells[i]]
    updated = list(cells)
    updated[i] = a
    return a, (updated[0], updated[1], updated[2])


def run(program: tuple[str, ...], bits: tuple[int, ...], start: State = ZERO) -> State:
    """Run ``program`` from ``start``, reading ``bits`` in order."""
    state = start
    pos = 0
    for op in program:
        if op == "/":
            state = step(state, op, bits[pos])
            pos += 1
        else:
            state = step(state, op)
    return state
