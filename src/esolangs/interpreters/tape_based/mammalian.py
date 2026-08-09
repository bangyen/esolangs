"""Interpreter for MAMMALIAN.

SEED/CONFLAGRATE operate on all 23 arrays, EXCRETE/CONSUME/FISSION/DIGEST on
the current one, SPRINT moves the pointer, LEAPFROG jumps, ACCEPT reads a byte
of input, and PRONOUNCE prints the accumulator as a byte.
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
                flat[n] = (x + num) % 256
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


def run(code: str, io: IO) -> None:
    """Run a MAMMALIAN program."""
    ins = (
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

    tokens = re.findall(f'({"|".join(ins)})', code)
    lst: list[list[int]] = [[0] for _ in range(23)]
    ind = ptr = acc = 0

    while ind < len(tokens):
        n = ins.index(tokens[ind])
        curr = lst[ptr]
        if n < 2:
            total(n, lst)
        elif n < 6:
            acc = partial(n, curr, acc)
        elif n == 6 and acc < len(curr):
            ptr = (ptr + curr[acc]) % 23
        elif n == 7 and curr and curr[-1]:
            ind = acc - curr[0] - 1
            if ind < 0:
                break
        elif n == 8:
            val = io.input_str()
            if val:
                m = ord(val[0]) ^ acc
                lst[0].append(m % 256)
        elif n == 9:
            io.print_char(chr(acc % 256))

        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
