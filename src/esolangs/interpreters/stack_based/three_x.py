r"""Interpreter for 3x."""

from __future__ import annotations

import re
import sys
from fractions import Fraction

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# : The value ``^`` yields for.
_UNSET = 3

# : One instant of a run:.
# : the operand stack, the.
# : not a record: every.
# : editing one in place, and.
#: reason.
# :.
# : The variables are kept.
# : reported them, so one.
# :.
# : The code is deliberately.
# : so carrying it would put.
# : stores.
type _State = tuple[
    int,
    tuple[Fraction, ...],
    tuple[int, ...],
    tuple[tuple[Fraction, Fraction], ...],
]

# : How many stack items each.
# : two-item commands take two,.
# : one.
_NEEDS = {"x": 3, "v": 2, "#": 2, "!": 1, "^": 1, "(": 1, ")": 1}


def _needs(char: str) -> int:
    r"""Return how many stack items ``char`` requires to run."""
    return _NEEDS.get(char, 0)


def _forward(code: str, ind: int) -> int | None:
    r"""Return the position of the ``)`` matching the ``(`` at ``ind``."""
    num = 1
    while num > 0:
        ind += 1
        if ind >= len(code):
            return None
        if code[ind] == "(":
            num += 1
        elif code[ind] == ")":
            num -= 1
    return ind


def _stored(
    variables: tuple[tuple[Fraction, Fraction], ...],
    key: Fraction,
    value: Fraction,
) -> tuple[tuple[Fraction, Fraction], ...]:
    r"""Return ``variables`` with ``key`` bound to ``value``, in key order."""
    kept = tuple((k, v) for k, v in variables if k != key)
    return tuple(sorted((*kept, (key, value))))


def _loaded(
    variables: tuple[tuple[Fraction, Fraction], ...],
    key: Fraction,
) -> Fraction:
    r"""Return the value bound to ``key``, or 3 when it has none."""
    for k, value in variables:
        if k == key:
            return value
    return Fraction(_UNSET)


# Ruby's Rational() string.
# not decimals; the interpreter.
_RATIONAL = re.compile(r"^[+-]?\d+(?:/[+-]?\d+)?$")


class _Machine:
    r"""Per-run 3x state: the code, stack, jump stack, variables, and."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Store ``code`` and start with an empty stack and no variables."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per.
        # once by ``step``'s guard --.
        self.size = len(code)
        self.state: _State = (0, (), (), ())

    # The language's own names.
    # than fields of their own, so.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def stack(self) -> tuple[Fraction, ...]:
        r"""The operand stack, bottom first."""
        return self.state[1]

    @property
    def jumps(self) -> tuple[int, ...]:
        r"""The pending loop returns."""
        return self.state[2]

    @property
    def variables(self) -> dict[Fraction, Fraction]:
        r"""The bindings, by key."""
        return dict(self.state[3])

    @property
    def halted(self) -> bool:
        r"""Whether the cursor has reached the end of the code."""
        return self.state[0] >= self.size

    # The VM's language-shaped.
    # is empty.

    @property
    def ip(self) -> int:
        r"""The code cursor."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        r"""No addressable cells; the store is the stack."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        # All three stores are already.
        # in key order, so the state.
        return self.state

    def step(self) -> None:
        r"""Execute one command, advancing (or jumping) the cursor."""
        if self.halted:
            return
        ind, stack, jumps, variables = self.state
        char = self.code[ind]
        if len(stack) < _needs(char):
            raise HaltError("empty stack")
        if char == "x" and stack[-3] == 0:
            # ``x`` divides by the third.
            # anything is popped.
            raise HaltError("division by zero")
        if char == ")" and stack[-1] != 0 and not jumps:
            raise HaltError("unmatched )")
        value = None
        target = None
        if char == "(" and stack[-1] == 0:
            target = _forward(self.code, ind)
            if target is None:
                # The original's scan walked.
                # noticing, so a caller.
                self.state = (len(self.code), stack, jumps, variables)
                raise HaltError("unmatched (")
        elif char == "?":
            line = self.io.input_str().strip()
            if not _RATIONAL.fullmatch(line):
                raise ValueError("input must be an integer or a fraction")
            if "/" in line and int(line.rsplit("/", 1)[1]) == 0:
                raise ValueError("input must be an integer or a fraction")
            value = Fraction(line)
        elif char == "!":
            top = stack[-1]
            if top.denominator == 1:
                self.io.print_num(top.numerator)
            else:
                self.io.print_str(str(top))
        elif char == "[":
            close = self.code.find("]", ind + 1)
            self.io.print_str("" if close == -1 else self.code[ind + 1 : close])
        self.state = _advance(self.state, self.code, value, target)


def _advance(
    state: _State,
    code: str,
    value: Fraction | None = None,
    target: int | None = None,
) -> _State:
    r"""Return the state after executing the command at the cursor."""
    ind, stack, jumps, variables = state
    char = code[ind]
    if char == "3":
        stack = (*stack, Fraction(3))
    elif char == "x":
        a, b, c = stack[-3], stack[-2], stack[-1]
        stack = (*stack[:-3], (c - b) / a)
    elif char == "?":
        stack = (*stack, value if value is not None else Fraction(0))
    elif char == "!":
        stack = stack[:-1]
    elif char == "v":
        variables = _stored(variables, stack[-2], stack[-1])
        stack = stack[:-2]
    elif char == "^":
        stack = (*stack[:-1], _loaded(variables, stack[-1]))
    elif char == "#":
        stack = (*stack[:-2], stack[-1], stack[-2])
    elif char == "(":
        if stack[-1] != 0:
            jumps = (*jumps, ind)
        elif target is not None:
            ind = target
    elif char == ")":
        if stack[-1] != 0:
            ind = jumps[-1]
        elif jumps:
            jumps = jumps[:-1]
    elif char == "[":
        close = code.find("]", ind + 1)
        if close != -1:
            ind = close
    return (ind + 1, stack, jumps, variables)


def run(code: str, io: IO) -> None:
    r"""Run a 3x program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
