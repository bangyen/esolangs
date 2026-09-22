"""Interpreter for 3x.

A stack language over exact rationals.  ``3`` pushes 3, ``x`` replaces
``a, b, c`` (c on top) with ``(c-b)/a``, ``?`` reads a rational, ``!``
pops and prints (integer when whole), ``v`` stores the top under a popped
key, ``^`` pushes a key's value (3 if unset), ``#`` swaps, ``(``/``)``
loop while the top is nonzero, ``[`` prints the literal up to ``]``.

Underflow, an unmatched ``(``, a stray ``)`` and division by zero raise
:class:`HaltError`; ``?`` raises :class:`EOFError` at end of input (the
cross-check exits 3) and rejects anything but an integer or fraction;
``[`` with no ``]`` prints nothing; malformed programs raise
:class:`ValueError`.

:func:`_advance` is a pure, total transition over an immutable
``_State``; :func:`_needs` and :func:`_forward` let the shell reject
underflow and unmatched brackets first, and the shell checks the zero
divisor.  :class:`_Machine` rebinds one state per ``step()``.
"""

from __future__ import annotations

import re
from fractions import Fraction

from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

#: The value ``^`` yields for a key never assigned.
_UNSET = 3

#: One instant of a run: ``(ind, stack, jumps, variables)`` -- the cursor,
#: the operand stack, the loop-return stack, and the variables.  A value,
#: not a record: every transition below returns a new one rather than
#: editing one in place, and all three stores are tuples for the same
#: reason.
#:
#: The variables are kept sorted by key, which is how ``snapshot`` already
#: reported them, so one logical set of bindings has one spelling.
#:
#: The code is deliberately not in here.  It does not change during a run,
#: so carrying it would put constant data in every value the cycle detector
#: stores.  It is a parameter to the transition instead.
type _State = tuple[
    int,
    tuple[Fraction, ...],
    tuple[int, ...],
    tuple[tuple[Fraction, Fraction], ...],
]

#: How many stack items each command needs.  ``x`` takes three, the two
#: two-item commands take two, and the rest of the popping commands take
#: one.  A command absent from this mapping needs none.
_NEEDS = {"x": 3, "v": 2, "#": 2, "!": 1, "^": 1, "(": 1, ")": 1}


def _needs(char: str) -> int:
    """Return how many stack items ``char`` requires to run."""
    return _NEEDS.get(char, 0)


def _forward(code: str, ind: int) -> int | None:
    """Return the position of the ``)`` matching the ``(`` at ``ind``.

    ``None`` when unmatched; the caller raises :class:`HaltError`.
    """
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
    """Return ``variables`` with ``key`` bound to ``value``, in key order."""
    kept = tuple((k, v) for k, v in variables if k != key)
    return tuple(sorted((*kept, (key, value))))


def _loaded(
    variables: tuple[tuple[Fraction, Fraction], ...],
    key: Fraction,
) -> Fraction:
    """Return the value bound to ``key``, or 3 when it has none."""
    for k, value in variables:
        if k == key:
            return value
    return Fraction(_UNSET)


# Ruby's Rational() string parser accepts integers and "a/b" fractions only,
# not decimals; the interpreter rejects the same inputs.
_RATIONAL = re.compile(r"^[+-]?\d+(?:/[+-]?\d+)?$")


class _Machine:
    """Per-run 3x state: the code, stack, jump stack, variables, and cursor."""

    def __init__(self, code: str, io: IO) -> None:
        """Store ``code`` and start with an empty stack and no variables."""
        self.io = io
        self.code = code
        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(code)
        self.state: _State = (0, (), (), ())

    # The language's own names.  They are views on the current state rather
    # than fields of their own, so there is one place a step can change.

    @property
    def ind(self) -> int:
        return self.state[0]

    @property
    def stack(self) -> tuple[Fraction, ...]:
        """The operand stack, bottom first."""
        return self.state[1]

    @property
    def jumps(self) -> tuple[int, ...]:
        """The pending loop returns."""
        return self.state[2]

    @property
    def variables(self) -> dict[Fraction, Fraction]:
        """The bindings, by key."""
        return dict(self.state[3])

    @property
    def halted(self) -> bool:
        """Whether the cursor has reached the end of the code."""
        return self.state[0] >= self.size

    # The VM's language-shaped view: the store *is* the stack, so ``memory``
    # is empty.  ``stack`` above is the view.

    @property
    def ip(self) -> int:
        """The code cursor."""
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        """No addressable cells; the store is the stack."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # All three stores are already tuples, and the variables are kept
        # in key order, so the state goes in as it stands.
        return self.state

    def step(self) -> None:
        """Execute one command, advancing (or jumping) the cursor."""
        if self.halted:
            return
        ind, stack, jumps, variables = self.state
        char = self.code[ind]
        if len(stack) < _needs(char):
            raise HaltError("empty stack")
        if char == "x" and stack[-3] == 0:
            # ``x`` divides by the third item, so a zero there faults before
            # anything is popped.
            raise HaltError("division by zero")
        if char == ")" and stack[-1] != 0 and not jumps:
            raise HaltError("unmatched )")
        value = None
        target = None
        if char == "(" and stack[-1] == 0:
            target = _forward(self.code, ind)
            if target is None:
                # The original's scan walked the cursor to the end before
                # noticing, so a caller catching the error sees that.
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
    """Return the state after executing the command at the cursor.

    Total: the shell has rejected every error case, read ``?``'s ``value``
    and resolved forward jumps.  ``)`` on a nonzero top jumps to the
    matching ``(``'s index so the shared increment lands on the body.
    """
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
    """Run a 3x program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
