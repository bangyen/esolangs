"""Interpreter for 3x.

A stack language over exact rationals.  ``3`` pushes 3, ``x`` replaces
``a, b, c`` (c on top) with ``(c-b)/a``, ``?`` reads a rational, ``!``
pops and prints (integer when whole), ``v`` stores the top under a popped
key, ``^`` pushes a key's value (3 if unset), ``#`` swaps, ``(``/``)``
loop while the top is nonzero, ``[`` prints the literal up to ``]``.

Input/output:
    Input numbers are whitespace-delimited integer or fraction tokens; the
    spec does not define delimiters.  ``?`` at EOF raises (the cross-check
    exits 3).

Errors:
    ProgramError: ``?`` reads anything but an integer or fraction (nonzero
    denominator), and any other malformed program.
    InputExhaustedError: ``?`` at EOF.
    HaltError: underflow, an unmatched ``(``, a stray ``)``, division by zero.

Decisions:
    * ``[`` with no ``]`` prints nothing (the rest runs as code) and a stray
      ``]`` is ignored, the wiki naming neither.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from fractions import Fraction
from types import MappingProxyType
from typing import Any

from esolangs.exceptions import HaltError
from esolangs.languages.three_x.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

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


_STRUCTURE = re.compile(r"[\[()]")


type _Image = tuple[str, Mapping[int, int]]


def _prepare_source(code: str) -> _Image:
    """Index the ends of literals and loops without raising on missing ends."""
    ends: dict[int, int] = {}
    stack: list[int] = []
    at = 0
    can_close_literal = True
    while mark := _STRUCTURE.search(code, at):
        index = mark.start()
        at = mark.end()
        char = mark[0]
        if char == "[":
            if can_close_literal:
                close = code.find("]", at)
                if close == -1:
                    # Later literal openers cannot have a closer either.
                    can_close_literal = False
                else:
                    ends[index] = close
                    at = close + 1
        elif char == "(":
            stack.append(index)
        elif stack:
            ends[stack.pop()] = index
    return code, MappingProxyType(ends)


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


# Input tokens are integers or fractions with an unsigned denominator.
_RATIONAL = re.compile(r"^[+-]?\d+(?:/\d+)?$")


_WORKSPACE_MODEL = WorkspaceModel(
    "three-x-v1",
    ("instruction", "operands", "loop_returns", "variables", "input_cursor"),
)


class _Machine:
    """Per-run 3x state: the code, stack, jump stack, variables, and cursor."""

    def __init__(self, code: str | _Image, io: IO) -> None:
        """Store ``code`` and start with an empty stack and no variables."""
        self.io = io
        self.code, ends = (code, None) if isinstance(code, str) else code
        self.ends: Mapping[int, int] | None = ends
        # ``halted`` is read twice per command -- once by ``run``'s loop and
        # once by ``step``'s guard -- so the length is taken once here.
        self.size = len(self.code)
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

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic components independently of storage and cycle grouping."""
        return _WORKSPACE_MODEL.capture(
            instruction=self.state[0],
            operands=self.state[1],
            loop_returns=self.state[2],
            variables=frozenset(self.state[3]),
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # ?(!?)! can revisit this state while consuming 1 1 0; the input
        # cursor separates the repeat from the later zero that ends the loop.
        return (*self.state, self.io.progress())

    def step(self) -> None:
        """Execute one command, advancing (or jumping) the cursor."""
        if self.halted:
            return
        ind, stack, jumps, variables = self.state
        char = self.code[ind]
        if len(stack) < _NEEDS.get(char, 0):
            raise HaltError(
                "empty stack",
                hint="push a value before reading or removing the stack top",
            )
        if char == "x" and stack[-3] == 0:
            # ``x`` divides by the third item, so a zero there faults before
            # anything is popped.
            raise HaltError(
                "division by zero", hint="ensure the divisor is nonzero before dividing"
            )
        if char == ")" and stack[-1] != 0 and not jumps:
            raise HaltError(
                "unmatched )",
                hint="pair each loop or group opener with its corresponding closer",
            )
        value = None
        target = None
        if char == "(":
            # Matchedness is settled on entry, whichever way the top goes:
            # a loop entered on a nonzero top otherwise ran off the end of
            # the code and halted as if its body had finished.
            # One-shot runs can print literals without building an index.
            if self.ends is None:
                _, self.ends = _prepare_source(self.code)
            match = self.ends.get(ind)
            if match is None:
                # The original's scan walked the cursor to the end before
                # noticing, so a caller catching the error sees that.
                self.state = (self.size, stack, jumps, variables)
                raise HaltError(
                    "unmatched (",
                    hint="pair each loop or group opener with its corresponding closer",
                )
            if stack[-1] == 0:
                target = match
        elif char == "?":
            line = self.io.input_token().strip()
            if not _RATIONAL.fullmatch(line) or (
                "/" in line and int(line.rsplit("/", 1)[1]) == 0
            ):
                raise syntax_error(
                    "input must be an integer or a fraction",
                    (
                        "supply a decimal integer or a fraction with nonzero "
                        "denominator, for example 3/2"
                    ),
                )
            value = Fraction(line)
        elif char == "!":
            top = stack[-1]
            if top.denominator == 1:
                self.io.print_num(top.numerator)
            else:
                self.io.print_str(str(top))
        elif char == "[":
            if self.ends is None:
                close = self.code.find("]", ind + 1)
                target = None if close == -1 else close
            else:
                target = self.ends.get(ind)
            self.io.print_str("" if target is None else self.code[ind + 1 : target])
        self.state = _advance(self.state, self.code, value, target)


# :func:`_advance` is a pure, total transition over an immutable ``_State``; ``_NEEDS``
# and the source index let the shell reject underflow and unmatched brackets first, and
# the shell checks the zero divisor.  :class:`_Machine` rebinds one state per
# ``step()``.
def _advance(
    state: _State,
    code: str,
    value: Fraction | None = None,
    target: int | None = None,
) -> _State:
    """Return the state after executing the command at the cursor.

    Total: the shell has rejected every error case, read ``?``'s ``value``
    and resolved forward jumps and literal ends.  ``)`` on a nonzero top jumps to the
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
    elif char == "[" and target is not None:
        ind = target
    return (ind + 1, stack, jumps, variables)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain source and bracket offsets for each invocation."""
    if not isinstance(source, str):
        raise TypeError("three_x machines require text source")
    if options:
        raise TypeError("three_x machines accept no runtime options")

    image = _prepare_source(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | _Image, io: IO) -> CompletionReport:
    """Run a 3x program."""
    machine = _Machine(code, io)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run a 3x program."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
