"""Interpreter for SLOW ACV MAMMALIAN.

SEED/CONFLAGRATE operate on all 23 arrays, EXCRETE/CONSUME/FISSION/DIGEST
on the current one, SPRINT moves the pointer, LEAPFROG jumps, ACCEPT reads
a byte, PRONOUNCE prints the accumulator as a byte.  SPRINT with a
too-large ``x`` is a NOP (per the wiki); LEAPFROG to a negative target is
undefined there, so it halts.  Exhausted input raises :class:`EOFError`.
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

    SEED adds each array's one-based index to its head mod 256.
    CONFLAGRATE flattens all 23, walks from both ends, and cuts back to the
    original lengths; its asymmetric pairing (the larger side loses
    ``x // y`` unwrapped, the smaller gains ``y % x``) can leave ``0..255``
    and reproducing that is the point.
    """
    if not op:
        # Spelled as a loop rather than the genexpr this reads as, because
        # SEED is the whole cost of a run: the boolean example runs it 1317
        # times, and a generator suspends and resumes once per array, so
        # the comprehension spent 42% of the run in 31608 frame
        # resumptions -- more than the arithmetic it was carrying.  The
        # arrays are 23 short tuples, so building the list directly is the
        # same work without the frames.
        seeded = []
        for num, arr in enumerate(arrays):
            seeded.append(((arr[0] + num + 1) % 256, *arr[1:]) if arr else arr)
        return tuple(seeded)

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

    EXCRETE (2) appends the accumulator as a byte and clears it, CONSUME (3)
    pops the middle cell (``(len - 1) // 2``), FISSION (4) halves it onto
    both ends, DIGEST folds with XOR.  CONSUME and FISSION on an empty array
    leave the state alone.
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

# Token -> opcode, so a step names its instruction by lookup.  ``step``
# used ``_INS.index(...)``, which walks the tuple comparing strings, and
# does it once per token executed: SEED is first and costs one compare,
# but PRONOUNCE is last and costs ten, so the price depended on which
# instruction was running rather than on the work it did.
_OPCODE = {name: op for op, name in enumerate(_INS)}


@functools.lru_cache(maxsize=16)
def _tokens(code: str) -> tuple[str, ...]:
    """Return the reusable instruction tokens in ``code``."""
    return tuple(re.findall(f"({'|'.join(_INS)})", code))


def _advance(state: _State, n: int, byte: int | None = None) -> _State:
    """Return the state after executing the token with opcode ``n``.

    Pure; PRONOUNCE changes only the cursor and ACCEPT's byte arrives as
    ``byte``.  Two positional rules from the original are required: SPRINT's
    guard ``acc < len(curr)`` passes a negative accumulator, which then
    indexes from the far end; LEAPFROG jumps to ``acc - head - 1`` and then
    takes the trailing advance, so the cursor ends at ``target + 1``.
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
        self.tokens = _tokens(code)
        self.lst: _Arrays = tuple((0,) for _ in range(23))
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
            self.lst,
            self.ptr,
            self.acc,
            self.io.position(),
            self._halted_by_command,
        )

    @property
    def _state(self) -> _State:
        """The machine's fields as the value the transitions work on."""
        return (
            self.lst,
            self.ptr,
            self.acc,
            self.ind,
            self._halted_by_command,
        )

    def _restore(self, state: _State) -> None:
        """Write a transition's result back onto the machine's fields."""
        self.lst, self.ptr, self.acc, self.ind, self._halted_by_command = state

    def step(self) -> None:
        """Execute one token, advancing (or jumping) the cursor."""
        if self.halted:
            return
        n = _OPCODE[self.tokens[self.ind]]

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
    tokens = _tokens(code)
    arrays = [[0] for _ in range(23)]
    ind = ptr = acc = 0
    while ind < len(tokens):
        n = _OPCODE[tokens[ind]]
        curr = arrays[ptr]
        if n == 0:
            for num, arr in enumerate(arrays, 1):
                if arr:
                    arr[0] = (arr[0] + num) % 256
        elif n == 1:
            rebuilt = _total(1, tuple(tuple(arr) for arr in arrays))
            arrays = [list(arr) for arr in rebuilt]
        elif n < 6:
            updated, acc = _partial(n, tuple(curr), acc)
            arrays[ptr] = list(updated)
        elif n == 6 and acc < len(curr):
            ptr = (ptr + curr[acc]) % 23
        elif n == 7 and curr and curr[-1]:
            target = acc - curr[0] - 1
            if target < 0:
                return
            ind = target
        elif n == 8:
            val = io.input_str()
            if val:
                arrays[0].append((ord(val[0]) ^ acc) % 256)
        elif n == 9:
            io.print_char(chr(acc % 256))
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
