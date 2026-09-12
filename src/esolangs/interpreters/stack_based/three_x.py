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

The execution model is a pure function over an immutable ``_State``:
:func:`_advance` maps a state and the code to the next state, and never
mutates what it is given.  It takes no ``io`` argument at all, so it is
total and side-effect free by construction rather than by inspection.

Keeping the transition total takes two pieces, because 3x has seven ways
to fail.  :func:`_needs` says how many stack items a command requires, so
the shell can reject an underflow before calling the transition, and
:func:`_forward` returns ``None`` for an unmatched ``(`` so the shell
raises rather than the transition faulting mid-scan.  The one failure that
depends on a *value* rather than a count -- ``x`` dividing by zero -- is
checked in the shell too, where the operands are already in hand.

:class:`_Machine` is the mutable shell the interpreter protocol requires.
It holds one ``_State`` and rebinds it each step, so the mutation lives in
exactly one assignment and every rule about what 3x *does* stays in the
pure layer.
"""

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
    """Return how many stack items ``char`` requires to run."""
    return _NEEDS.get(char, 0)


def _forward(code: str, ind: int) -> int | None:
    """Return the position of the ``)`` matching the ``(`` at ``ind``.

    ``None`` when the bracket is unmatched, which the caller turns into a
    :class:`HaltError` -- returning it rather than raising is what keeps
    the transition below free of error cases.
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


# Ruby's Rational() string.
# not decimals; the interpreter.
_RATIONAL = re.compile(r"^[+-]?\d+(?:/[+-]?\d+)?$")


class _Machine:
    """Per-run 3x state: the code, stack, jump stack, variables, and cursor."""

    def __init__(self, code: str, io: IO) -> None:
        """Store ``code`` and start with an empty stack and no variables."""
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

    # The VM's language-shaped.
    # is empty.

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
        # All three stores are already.
        # in key order, so the state.
        return self.state

    def step(self) -> None:
        """Execute one command, advancing (or jumping) the cursor.

        The two I/O commands and every error case live here rather than in
        the transition: this is the shell, so it is where an effect or a
        raise belongs, and it leaves :func:`_advance` total.
        """
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
    """Return the state after executing the command at the cursor.

    Pure, and total: the shell has already rejected every underflow, the
    division by zero and the unmatched brackets, read any input value, and
    resolved any forward jump.  It takes no ``io`` argument, so ``!`` and
    ``[`` are the caller's business -- neither changes state beyond the
    cursor -- and ``?``'s value arrives as ``value``.

    A ``)`` on a nonzero top jumps back to the matching ``(``'s own index,
    so the shared increment lands on the first command of the body and the
    bracket is not re-tested; on a zero top it drops the pending jump.
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
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
