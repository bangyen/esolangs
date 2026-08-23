"""Interpreter for Nevermind.

Line-based commands: ``print`` joins its arguments and writes them with no
separator or trailing newline (the wiki says only "Outputs *text* to the
screen", and its Hello-World example shows none), ``input`` stores a line in
the answer variable, ``make`` computes arithmetic (``+ - * /`` on numbers,
``++`` concatenating strings), and ``if``/``loop``/``endloop`` branch on
comparisons.  ``$name`` references a variable.

An ``if``/``loop``/``endloop`` with no matching partner is a structurally
malformed program and is rejected with :class:`ValueError`; dividing by zero,
referencing an undefined ``$name``, or ``input`` with no prompt are invalid
operations that halt the program with :class:`~esolangs.exceptions.HaltError`
(or, for the missing prompt, :class:`ValueError`).

Exhausted input raises :class:`EOFError` (the repo-wide convention).

The interpreter runs on a :class:`_Machine` (the parsed program, the
variables, and the loop/skip cursor state), so it is step-capable:
``step()`` executes one line and ``halted`` is true once the cursor
reaches the end of the program.
"""

import sys
from typing import cast

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def find(code: list[list[str | int | float]], ind: int) -> int:
    """Return the index of the matching ``if``/``loop`` partner for ``ind``.

    Raises :class:`ValueError` when the partner is missing: the wiki defines
    ``if``/``endif`` and ``loop``/``endloop`` only for matched pairs, so an
    unmatched marker is a malformed program.
    """
    if "end" in (op := str(code[ind][0])):
        match = op[3:]
        move = -1
    else:
        match = "end" + op
        move = 1

    num = move
    ind += move

    while num:
        if not 0 <= ind < len(code):
            raise ValueError(f"unmatched {op}")
        if code[ind][0] == op:
            num += move
        elif code[ind][0] == match:
            num -= move
        ind += move
    return ind - 1


class _Machine:
    """Per-run Nevermind state: the parsed program, variables, and cursor."""

    def __init__(self, lines: list[str], io: IO) -> None:
        """Parse ``lines`` into comma-separated command tokens."""
        self.io = io
        self.ind = 0
        self.var: dict[str, int | float | str] = {}
        self.skip = False
        self.code: list[list[str | int | float]] = []

        for raw in lines:
            line = raw.lstrip().rstrip("\n").split(",")
            self.code.append([v.replace("*44", ",") for v in line if v])

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the program."""
        return self.ind >= len(self.code)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            self.skip,
            tuple(sorted(self.var.items())),
            tuple(tuple(c) for c in self.code),
        )

    def step(self) -> None:
        """Execute one line, resolving ``$name`` references in place."""
        if self.halted:
            return
        if (c := self.code[self.ind]) and not self.skip:
            for i, val in enumerate(c[1:]):
                if isinstance(val, str):
                    if val[0] == "$":
                        name = val[1:].strip()
                        if name not in self.var:
                            raise HaltError
                        c[i + 1] = self.var[name]
                    nxt = c[i + 1]
                    if isinstance(nxt, str) and nxt.isascii() and nxt.isdigit():
                        c[i + 1] = int(nxt)

            if (op := c[0]) == "print":
                self.io.print_str("".join(map(str, c[1:])))
            elif op == "input":
                if len(c) < 2:
                    raise ValueError("input requires a prompt")
                self.var["answer"] = self.io.input_str(cast(str, c[1]))
            elif op == "make":
                if len(c) == 5:
                    v: int | float | str
                    if (o := c[3]) == "+":
                        v = cast(int | float, c[2]) + cast(int | float, c[4])
                    elif o == "-":
                        v = cast(int | float, c[2]) - cast(int | float, c[4])
                    elif o == "*":
                        v = cast(int | float, c[2]) * cast(int | float, c[4])
                    elif o == "++":
                        v = str(c[2]) + str(c[4])
                    else:
                        n = cast(int | float, c[4])
                        if n == 0:
                            raise HaltError
                        v = cast(int | float, c[2]) / n
                    self.var[cast(str, c[1])] = v
                else:
                    self.var[cast(str, c[1])] = c[2]
            elif op == "if":
                lhs, cmp_op, rhs = c[1:4]
                if cmp_op == ">":
                    b = cast(int | float, lhs) > cast(int | float, rhs)
                elif cmp_op == "<":
                    b = cast(int | float, lhs) < cast(int | float, rhs)
                else:
                    b = lhs == rhs
                if not b:
                    self.ind = find(self.code, self.ind)
            elif op == "loop":
                if c[1]:
                    c[1] = cast(int | float, c[1]) - 1
                else:
                    self.ind = find(self.code, self.ind)
                    self.skip = True
            elif op == "endloop":
                self.ind = find(self.code, self.ind) + 1
        self.skip = False
        self.ind += 1


def run(lines: list[str], io: IO) -> None:
    """Run a Nevermind program given its comma-separated command lines."""
    machine = _Machine(lines, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.readlines()
            run(data, IO())
