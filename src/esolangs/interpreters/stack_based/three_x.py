"""Interpreter for 3x.

A stack-based language over exact rationals.  ``3`` pushes the rational 3,
``x`` replaces the top three items ``a, b, c`` (c on top) with ``(c-b)/a``,
``?`` reads a rational from input, ``!`` pops and prints the top (as an
integer when whole, otherwise as a fraction), ``v`` stores the top under a
popped key, ``^`` pushes the value of a popped key (3 if unassigned), ``#``
swaps the top two, ``(``/``)`` loop while the top is nonzero, and ``[``
prints the literal up to the next ``]`` and skips past it.

Semantics:
- an empty-stack pop, a swap or ``x`` with too few items, a ``(``/``)`` on
  an empty stack, an unmatched ``(``, a ``)`` with no pending ``(``, or a
  division by zero raise :class:`HaltError`;
- ``?`` raises :class:`EOFError` when input runs out, where the cross-check
  exits with status 3, and rejects input that is not an integer or a
  fraction (matching the cross-check's ``Rational`` parser, which rejects
  decimals);
- ``[`` with no closing ``]`` prints nothing.

Malformed programs raise :class:`ValueError`.

The interpreter runs on a :class:`_Machine` (the code, stack, jump stack,
variables, and cursor), so it is step-capable: ``step()`` executes one
command and ``halted`` is true once the cursor reaches the end of the code.
"""

import re
import sys
from fractions import Fraction

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# Ruby's Rational() string parser accepts integers and "a/b" fractions only,
# not decimals; the interpreter rejects the same inputs.
_RATIONAL = re.compile(r"^[+-]?\d+(?:/[+-]?\d+)?$")


class _Machine:
    """Per-run 3x state: the code, stack, jump stack, variables, and cursor."""

    def __init__(self, code: str, io: IO) -> None:
        """Store ``code`` and start with an empty stack and no variables."""
        self.io = io
        self.code = code
        self.stack: list[Fraction] = []
        self.jumps: list[int] = []
        self.variables: dict[Fraction, Fraction] = {}
        self.ind = 0

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.ind >= len(self.code)

    # The VM's language-shaped view: the store *is* the stack, so ``memory``
    # is empty.  ``stack`` above is handed back live -- the VM copies what
    # it exposes, which is why the shape protocol asks only for a Sequence.

    @property
    def ip(self) -> int:
        """The code cursor."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """No addressable cells; the store is the stack."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.ind,
            tuple(self.stack),
            tuple(self.jumps),
            tuple(sorted(self.variables.items())),
        )

    def _pop(self) -> Fraction:
        if not self.stack:
            raise HaltError("empty stack")
        return self.stack.pop()

    def step(self) -> None:
        """Execute one command, advancing (or jumping) the cursor."""
        if self.halted:
            return
        char = self.code[self.ind]
        if char == "3":
            self.stack.append(Fraction(3))
        elif char == "x":
            c = self._pop()
            b = self._pop()
            a = self._pop()
            if a == 0:
                raise HaltError("division by zero")
            self.stack.append((c - b) / a)
        elif char == "?":
            line = self.io.input_str().strip()
            if not _RATIONAL.fullmatch(line):
                raise ValueError("input must be an integer or a fraction")
            if "/" in line and int(line.rsplit("/", 1)[1]) == 0:
                raise ValueError("input must be an integer or a fraction")
            self.stack.append(Fraction(line))
        elif char == "!":
            value = self._pop()
            if value.denominator == 1:
                self.io.print_num(value.numerator)
            else:
                self.io.print_str(str(value))
        elif char == "v":
            value = self._pop()
            key = self._pop()
            self.variables[key] = value
        elif char == "^":
            key = self._pop()
            self.stack.append(self.variables.get(key, Fraction(3)))
        elif char == "#":
            x = self._pop()
            y = self._pop()
            self.stack.append(x)
            self.stack.append(y)
        elif char == "(":
            if not self.stack:
                raise HaltError("empty stack")
            if self.stack[-1] != 0:
                self.jumps.append(self.ind)
            else:
                num = 1
                while num > 0:
                    self.ind += 1
                    if self.ind >= len(self.code):
                        raise HaltError("unmatched (")
                    inner = self.code[self.ind]
                    if inner == "(":
                        num += 1
                    elif inner == ")":
                        num -= 1
        elif char == ")":
            if not self.stack:
                raise HaltError("empty stack")
            if self.stack[-1] != 0:
                if not self.jumps:
                    raise HaltError("unmatched )")
                self.ind = self.jumps[-1]
            elif self.jumps:
                self.jumps.pop()
        elif char == "[":
            close = self.code.find("]", self.ind + 1)
            if close == -1:
                self.io.print_str("")
            else:
                self.io.print_str(self.code[self.ind + 1 : close])
                self.ind = close
        self.ind += 1


def run(code: str, io: IO) -> None:
    """Run a 3x program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
