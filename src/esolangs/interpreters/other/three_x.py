"""Interpreter for 3x.

A stack-based language over exact rationals.  ``3`` pushes the rational 3,
``x`` replaces the top three items ``a, b, c`` (c on top) with ``(c-b)/a``,
``?`` reads a rational from input, ``!`` pops and prints the top (as an
integer when whole, otherwise as a fraction), ``v`` stores the top under a
popped key, ``^`` pushes the value of a popped key (3 if unassigned), ``#``
swaps the top two, ``(``/``)`` loop while the top is nonzero, and ``[``
prints the literal up to the next ``]`` and skips past it.

Semantics match the Ruby cross-check (``extra/ruby/3x.rb``):
- an empty-stack pop, a swap or ``x`` with too few items, a ``(``/``)`` on
  an empty stack, an unmatched ``(``, a ``)`` with no pending ``(``, or a
  division by zero raise :class:`HaltError`;
- ``?`` raises :class:`EOFError` when input runs out, where the reference
  exits with status 3, and accepts decimal input that the reference rejects;
- ``[`` with no closing ``]`` prints nothing.
"""

import sys
from fractions import Fraction

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def run(code: str, io: IO) -> None:
    """Run a 3x program."""
    stack: list[Fraction] = []
    jumps: list[int] = []
    variables: dict[Fraction, Fraction] = {}
    ind = 0
    n = len(code)

    def pop() -> Fraction:
        if not stack:
            raise HaltError("empty stack")
        return stack.pop()

    while ind < n:
        char = code[ind]
        if char == "3":
            stack.append(Fraction(3))
        elif char == "x":
            c = pop()
            b = pop()
            a = pop()
            if a == 0:
                raise HaltError("division by zero")
            stack.append((c - b) / a)
        elif char == "?":
            line = io.input_str("Input: ").strip()
            stack.append(Fraction(line))
        elif char == "!":
            value = pop()
            if value.denominator == 1:
                io.print_num(value.numerator)
            else:
                io.print_str(str(value))
        elif char == "v":
            value = pop()
            key = pop()
            variables[key] = value
        elif char == "^":
            key = pop()
            stack.append(variables.get(key, Fraction(3)))
        elif char == "#":
            x = pop()
            y = pop()
            stack.append(x)
            stack.append(y)
        elif char == "(":
            if not stack:
                raise HaltError("empty stack")
            if stack[-1] != 0:
                jumps.append(ind)
            else:
                num = 1
                while num > 0:
                    ind += 1
                    if ind >= n:
                        raise HaltError("unmatched (")
                    inner = code[ind]
                    if inner == "(":
                        num += 1
                    elif inner == ")":
                        num -= 1
        elif char == ")":
            if not stack:
                raise HaltError("empty stack")
            if stack[-1] != 0:
                if not jumps:
                    raise HaltError("unmatched )")
                ind = jumps[-1]
            elif jumps:
                jumps.pop()
        elif char == "[":
            close = code.find("]", ind + 1)
            if close == -1:
                io.print_str("")
            else:
                io.print_str(code[ind + 1 : close])
                ind = close
        ind += 1


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
