"""Interpreter for Nevermind.

Line-based commands: ``print`` joins its arguments and writes them with no
separator or trailing newline (the wiki says only "Outputs *text* to the
screen", and its Hello-World example shows none), ``input`` stores a line in
the answer variable, ``make`` computes arithmetic (``+ - * /`` on numbers,
``++`` concatenating strings), and ``if``/``loop``/``endloop`` branch on
comparisons.  ``$name`` references a variable.

The wiki never states operand types: its only arithmetic example is a
calculator whose operands come from ``input``, so any of them can be
text.  Since the language has ``++`` for joining strings, ``+ - * /`` and
the ordered comparisons ``<``/``>`` are read as numeric, and a string
reaching one of them halts with :class:`~esolangs.exceptions.HaltError`
rather than falling through to Python's meaning for it (which would
concatenate, repeat, or order the operands instead).  ``=`` is not an
ordering, so it still compares strings.

A number is written in ASCII, either as digits or as digits around a
single ``.``; a decimal is only read as one when the spelling matches how
it prints back, so ``02.5`` stays the text the program wrote.

An ``if``/``loop``/``endloop`` with no matching partner, or a command
short of the operands its form requires (``make`` without a value,
``if`` without both sides of its comparison, ``loop`` without a count),
is a structurally malformed program and is rejected with
:class:`ValueError`; dividing by zero,
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


def _as_number(value: str) -> int | float | None:
    """Return ``value`` as a number, or ``None`` if it does not spell one.

    Only ASCII spellings count: :meth:`str.isdigit` is also true for
    superscript and Arabic-Indic digits, which :func:`int` either rejects
    or reads as a value the program never wrote, so those stay strings.
    """
    if not value.isascii():
        return None
    if value.isdigit():
        return int(value)
    whole, dot, frac = value.partition(".")
    if dot and whole.isdigit() and frac.isdigit():
        # Only a spelling that survives the round trip: ``str`` renders a
        # float back without the written leading zeros, so "02.5" would
        # print as "2.5" and silently lose a character the program wrote.
        number = float(value)
        if str(number) == value:
            return number
    return None


def _number(value: str | int | float, op: str) -> int | float:
    """Return ``value`` as a number, halting if it is not one.

    ``+ - * /`` and the ``<``/``>`` comparisons are arithmetic: the wiki
    gives Nevermind ``++`` for joining strings, so a string reaching one of
    the numeric operators has no defined result and the program halts
    rather than falling through to Python's own meaning for it (which would
    concatenate, repeat, or order the operands instead).
    """
    if isinstance(value, str):
        raise HaltError(f"{op} needs a number, got {value!r}")
    return value


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
                    if isinstance(nxt, str) and (num := _as_number(nxt)) is not None:
                        c[i + 1] = num

            if (op := c[0]) == "print":
                self.io.print_str("".join(map(str, c[1:])))
            elif op == "input":
                if len(c) < 2:
                    raise ValueError("input requires a prompt")
                self.var["answer"] = self.io.input_str(str(c[1]))
            elif op == "make":
                if len(c) < 3:
                    raise ValueError("make requires a name and a value")
                if len(c) == 5:
                    v: int | float | str
                    if (o := c[3]) == "++":
                        v = str(c[2]) + str(c[4])
                    else:
                        name = str(o)
                        left, right = _number(c[2], name), _number(c[4], name)
                        if o == "+":
                            v = left + right
                        elif o == "-":
                            v = left - right
                        elif o == "*":
                            v = left * right
                        else:
                            if right == 0:
                                raise HaltError
                            v = left / right
                    self.var[str(c[1])] = v
                else:
                    self.var[str(c[1])] = c[2]
            elif op == "if":
                if len(c) < 4:
                    raise ValueError("if requires two operands and a comparison")
                lhs, cmp_op, rhs = c[1:4]
                if cmp_op == ">":
                    b = _number(lhs, ">") > _number(rhs, ">")
                elif cmp_op == "<":
                    b = _number(lhs, "<") < _number(rhs, "<")
                else:
                    b = lhs == rhs
                if not b:
                    self.ind = find(self.code, self.ind)
            elif op == "loop":
                if len(c) < 2:
                    raise ValueError("loop requires a count")
                if c[1]:
                    c[1] = _number(c[1], "loop") - 1
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
