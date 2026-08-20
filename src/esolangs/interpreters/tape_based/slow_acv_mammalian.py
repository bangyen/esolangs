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


def total(op: int, lst: list[list[int]]) -> None:
    """Apply SEED (``op == 0``) or CONFLAGRATE to all 23 arrays."""
    if op:
        size = list(map(len, lst))
        flat: list[int] = functools.reduce(operator.iadd, lst, [])
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

        for k in range(23):
            lst[k] = flat[: size[k]]
            flat = flat[size[k] :]
    else:
        for num in range(23):
            if lst[num]:
                lst[num][0] += num + 1
                lst[num][0] %= 256


def partial(op: int, curr: list[int], acc: int) -> int:
    """Apply an EXCRETE/CONSUME/FISSION/DIGEST op to the current array."""
    if op == 2:
        curr.append(acc % 256)
        acc = 0
    elif op == 3:
        if not curr:
            return acc
        m = (len(curr) - 1) // 2
        acc = curr.pop(m)
    elif op == 4:
        if not curr:
            return acc
        m = (len(curr) - 1) // 2
        num = curr.pop(m) // 2
        curr.insert(0, num)
        curr.append(num)
    else:
        acc ^= sum(curr)

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

    def step(self) -> None:
        """Execute one token, advancing (or jumping) the cursor."""
        if self.halted:
            return
        n = _INS.index(self.tokens[self.ind])
        curr = self.lst[self.ptr]
        if n < 2:
            total(n, self.lst)
        elif n < 6:
            self.acc = partial(n, curr, self.acc)
        elif n == 6 and self.acc < len(curr):
            self.ptr = (self.ptr + curr[self.acc]) % 23
        elif n == 7 and curr and curr[-1]:
            target = self.acc - curr[0] - 1
            if target < 0:
                self._halted_by_command = True
                return
            self.ind = target
        elif n == 8:
            val = self.io.input_str()
            if val:
                m = ord(val[0]) ^ self.acc
                self.lst[0].append(m % 256)
        elif n == 9:
            self.io.print_char(chr(self.acc % 256))

        self.ind += 1


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
