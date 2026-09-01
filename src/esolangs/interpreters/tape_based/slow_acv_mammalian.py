"""Interpreter for SLOW ACV MAMMALIAN.

SEED/CONFLAGRATE operate on all 23 arrays, EXCRETE/CONSUME/FISSION/DIGEST on
the current one, SPRINT moves the pointer, LEAPFROG jumps, ACCEPT reads a byte
of input, and PRONOUNCE prints the accumulator as a byte.

The wiki defines SPRINT with a too-large ``x`` as a NOP (it does nothing when
the array has fewer than ``x`` variables), which this interpreter follows;
LEAPFROG with a negative jump target is undefined by the wiki, so the
interpreter halts instead of jumping.

Exhausted input raises :class:`EOFError` (the repo-wide convention).

The interpreter runs on a :class:`_Machine` (the 23 arrays, pointer,
accumulator, and token cursor), so it is step-capable: ``step()`` executes
one token and ``halted`` is true once the cursor reaches the end of the
token stream.
"""

import functools
import operator
import re
import sys

from esolangs.interpreters.io import IO

#: One instant of a run: ``(arrays, ptr, acc, ind, halted)`` -- the 23
#: arrays, the pointer that picks the current one, the accumulator, the
#: token cursor, and whether a negative LEAPFROG stopped the run.  A value
#: the transitions below map forward, never editing one in place, with the
#: arrays as nested ``tuple``s for the same reason.
#:
#: ``halted`` is carried because a negative LEAPFROG stops the run with the
#: cursor left where it was, so the position alone does not say.
#:
#: The token stream is not here: it is fixed for the whole run, so a step
#: takes the opcode it is executing as an argument instead.
type _Arrays = tuple[tuple[int, ...], ...]
type _State = tuple[_Arrays, int, int, int, bool]


def _total(op: int, arrays: _Arrays) -> _Arrays:
    """Return ``arrays`` after SEED (``op == 0``) or CONFLAGRATE.

    SEED adds each array's one-based index to its head, modulo a byte, and
    skips an empty array.  CONFLAGRATE flattens all 23 into one run, walks
    it from both ends at once, and cuts the result back into the original
    lengths -- so it moves values across array boundaries, which is why it
    cannot work array by array.

    The pairing arithmetic is deliberately asymmetric and only partly
    reduced: the larger side loses ``x // y`` with no wrap, the smaller
    gains ``y % x`` while the far end loses it.  Cells can leave ``0..255``
    that way, and reproducing that is the point.
    """
    if not op:
        return tuple(
            ((arr[0] + num + 1) % 256, *arr[1:]) if arr else arr
            for num, arr in enumerate(arrays)
        )

    size = [len(arr) for arr in arrays]
    flat: list[int] = functools.reduce(operator.iadd, (list(a) for a in arrays), [])
    m = len(flat)

    for k in range(m // 2):
        x, y = flat[k], flat[m - k - 1]
        n = m - k - 1

        if x > y and y:
            num = x // y
            flat[k] -= num
            flat[n] = (y + num) % 256
        elif x < y and x:
            num = y % x
            flat[k] += num
            flat[n] -= num

    out: list[tuple[int, ...]] = []
    for k in range(23):
        out.append(tuple(flat[: size[k]]))
        flat = flat[size[k] :]
    return tuple(out)


def _partial(op: int, curr: tuple[int, ...], acc: int) -> tuple[tuple[int, ...], int]:
    """Return the current array and accumulator after one array op.

    EXCRETE (2) appends the accumulator as a byte and clears it, CONSUME
    (3) pops the middle cell into the accumulator, FISSION (4) halves that
    same cell and hangs the halves off both ends, and DIGEST (anything
    else) folds the array into the accumulator with XOR.

    The middle is ``(len - 1) // 2``, the lower of the two on an even
    length.  CONSUME and FISSION have nothing to take from an empty array,
    so both leave the state alone rather than faulting.
    """
    if op == 2:
        return ((*curr, acc % 256), 0)
    if op == 3:
        if not curr:
            return (curr, acc)
        m = (len(curr) - 1) // 2
        return ((*curr[:m], *curr[m + 1 :]), curr[m])
    if op == 4:
        if not curr:
            return (curr, acc)
        m = (len(curr) - 1) // 2
        num = curr[m] // 2
        return ((num, *curr[:m], *curr[m + 1 :], num), acc)
    return (curr, acc ^ sum(curr))


def total(op: int, lst: list[list[int]]) -> None:
    """Apply SEED (``op == 0``) or CONFLAGRATE to all 23 arrays.

    A mutating shell over :func:`_total`, kept because it is this module's
    published shape for the whole-memory ops.
    """
    lst[:] = [list(arr) for arr in _total(op, tuple(tuple(a) for a in lst))]


def partial(op: int, curr: list[int], acc: int) -> int:
    """Apply an EXCRETE/CONSUME/FISSION/DIGEST op to the current array.

    A mutating shell over :func:`_partial`, which returns the new array
    rather than editing one; this writes it back and hands the caller the
    accumulator, as before.
    """
    after, acc = _partial(op, tuple(curr), acc)
    curr[:] = list(after)
    return acc


_INS = (
    "SEED",
    "CONFLAGRATE",
    "EXCRETE",
    "CONSUME",
    "FISSION",
    "DIGEST",
    "SPRINT",
    "LEAPFROG",
    "ACCEPT",
    "PRONOUNCE",
)


def _advance(state: _State, n: int, byte: int | None = None) -> _State:
    """Return the state after executing the token with opcode ``n``.

    Pure: it reads ``state`` and returns a new one.  It takes no ``io``
    argument, so PRONOUNCE changes nothing but the cursor -- printing is
    the caller's business -- and ACCEPT's byte arrives as ``byte``, already
    read and already XORed against nothing, since the accumulator it mixes
    with lives here.

    Two positional rules survive from the original and are load-bearing:

    * SPRINT's guard is ``acc < len(curr)``, which a *negative*
      accumulator also passes, and the index that follows then counts from
      the far end.  Guarding that away would change which array a program
      lands on.
    * LEAPFROG jumps to ``acc - head - 1`` and then takes the trailing
      advance like every other token, so the cursor ends at ``target + 1``.
      A negative target halts instead, with the cursor left where it was.
    """
    arrays, ptr, acc, ind, halted = state
    curr = arrays[ptr]

    if n < 2:
        arrays = _total(n, arrays)
    elif n < 6:
        curr, acc = _partial(n, curr, acc)
        arrays = (*arrays[:ptr], curr, *arrays[ptr + 1 :])
    elif n == 6 and acc < len(curr):
        if acc < -len(curr):
            # The array is a tuple here, so its own subscript would say
            # "tuple index out of range"; a run that walked off the end
            # said "list" before and callers see the message, so keep it.
            raise IndexError("list index out of range")
        ptr = (ptr + curr[acc]) % 23
    elif n == 7 and curr and curr[-1]:
        target = acc - curr[0] - 1
        if target < 0:
            return (arrays, ptr, acc, ind, True)
        ind = target
    elif n == 8 and byte is not None:
        head = (*arrays[0], (byte ^ acc) % 256)
        arrays = (head, *arrays[1:])

    return (arrays, ptr, acc, ind + 1, halted)


class _Machine:
    """One SLOW ACV MAMMALIAN run: the 23 arrays, pointer, acc, and cursor."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.tokens = re.findall(f"({'|'.join(_INS)})", code)
        self.lst: list[list[int]] = [[0] for _ in range(23)]
        self.ind = self.ptr = self.acc = 0
        self._halted_by_command = False

    @property
    def halted(self) -> bool:
        """Whether a negative LEAPFROG fired or the cursor reached the end."""
        return self._halted_by_command or self.ind >= len(self.tokens)

    # The VM's language-shaped view: 23 arrays + pointer; memory is the current array,
    # stack all 23.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.lst[self.ptr])

    @property
    def stack(self) -> list[object]:
        """The stack."""
        return [row for arr in self.lst for row in arr]

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            tuple(tuple(row) for row in self.lst),
            self.ptr,
            self.acc,
            self.io.position(),
            self._halted_by_command,
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transitions work on."""
        return (
            tuple(tuple(row) for row in self.lst),
            self.ptr,
            self.acc,
            self.ind,
            self._halted_by_command,
        )

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields.

        The fields are this class's published shape -- tests seed ``lst``
        and read ``ind`` -- so they stay; the one assignment a step makes
        is here rather than scattered through the rules above.
        """
        arrays, self.ptr, self.acc, self.ind, self._halted_by_command = state
        self.lst = [list(arr) for arr in arrays]

    def step(self) -> None:
        """Execute one token, advancing (or jumping) the cursor.

        The two ports live here rather than in the transition: this is the
        shell, so it is where an effect belongs.  ACCEPT's byte is read
        here and handed over, and PRONOUNCE prints the accumulator the
        transition is about to carry forward unchanged.
        """
        if self.halted:
            return
        n = _INS.index(self.tokens[self.ind])

        byte = None
        if n == 8:
            val = self.io.input_str()
            if val:
                byte = ord(val[0])
        elif n == 9:
            self.io.print_char(chr(self.acc % 256))

        self._restore(_advance(self._state, n, byte))


def run(code: str, io: IO) -> None:
    """Run a SLOW ACV MAMMALIAN program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
