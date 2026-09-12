r"""Interpreter for SLOW ACV MAMMALIAN."""

import functools
import operator
import re
import sys

from esolangs.interpreters.io import IO

# : One instant of a run:.
# : arrays, the pointer that.
# : token cursor, and whether a.
# : the transitions below map.
# : arrays as nested ``tuple``s.
# :.
# : ``halted`` is carried.
# : cursor left where it was,.
# :.
# : The token stream is not.
# : takes the opcode it is.
type _Arrays = tuple[tuple[int, ...], ...]
type _State = tuple[_Arrays, int, int, int, bool]


def _total(op: int, arrays: _Arrays) -> _Arrays:
    r"""Return ``arrays`` after SEED (``op == 0``) or CONFLAGRATE."""
    if not op:
        # Spelled as a loop rather than.
        # SEED is the whole cost of a.
        # times, and a generator.
        # the comprehension spent 42%.
        # resumptions -- more than the.
        # arrays are 23 short tuples,.
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
    r"""Return the current array and accumulator after one array op."""
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

# Token -> opcode, so a step.
# used ``_INS.index(...)``,.
# does it once per token.
# but PRONOUNCE is last and.
# instruction was running.
_OPCODE = {name: op for op, name in enumerate(_INS)}


def _advance(state: _State, n: int, byte: int | None = None) -> _State:
    r"""Return the state after executing the token with opcode ``n``."""
    arrays, ptr, acc, ind, halted = state
    curr = arrays[ptr]

    if n < 2:
        arrays = _total(n, arrays)
    elif n < 6:
        curr, acc = _partial(n, curr, acc)
        arrays = (*arrays[:ptr], curr, *arrays[ptr + 1 :])
    elif n == 6 and acc < len(curr):
        if acc < -len(curr):
            # The array is a tuple here, so.
            # "tuple index out of range"; a.
            # said "list" before and.
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
    r"""One SLOW ACV MAMMALIAN run: the 23 arrays, pointer, acc, and cursor."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.tokens = re.findall(f"({'|'.join(_INS)})", code)
        self.lst: _Arrays = tuple((0,) for _ in range(23))
        self.ind = self.ptr = self.acc = 0
        self._halted_by_command = False

    @property
    def halted(self) -> bool:
        r"""Whether a negative LEAPFROG fired or the cursor reached the end."""
        return self._halted_by_command or self.ind >= len(self.tokens)

    # The VM's language-shaped.
    # stack all 23.

    @property
    def ip(self) -> int:
        r"""The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        r"""The addressable cells."""
        return list(self.lst[self.ptr])

    @property
    def stack(self) -> list[object]:
        r"""The stack."""
        return [row for arr in self.lst for row in arr]

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
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
        r"""The machine's fields as the value the transitions work on."""
        return (
            self.lst,
            self.ptr,
            self.acc,
            self.ind,
            self._halted_by_command,
        )

    def _restore(self, state: _State) -> None:
        r"""Write a transition's result back onto the machine's fields."""
        self.lst, self.ptr, self.acc, self.ind, self._halted_by_command = state

    def step(self) -> None:
        r"""Execute one token, advancing (or jumping) the cursor."""
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
    r"""Run a SLOW ACV MAMMALIAN program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
