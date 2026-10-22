"""Interpreter for Fackward.

The program is a sequence of nonnegative decimal integers, functions and
``[...]`` blocks, separated by whitespace where two numbers meet.  It starts
as the forward stack, first token on top; the backward stack starts empty.
Each step looks at the forward top: a number is popped and printed as a
character; a function whose arguments sit directly behind it pops them and
pushes its results on the backward stack; anything else moves there
unchanged.  An empty forward stack swaps with the backward one, so each
pass reads the sequence the other way round.  The second of two swaps with
nothing printed or executed between them reads a character and pushes its
code point on the (empty) backward stack.  ``H`` halts.  The wiki's Hello
world and ``::`` loop run as stated, and the null program is a cat.

Commands:
    ``+ab`` ``a+b``, ``-a`` ``-a``, ``*ab`` ``a*b``, ``/ab`` ``a//b``,
    ``%a`` 1 if ``a`` is 0 else 0, all on numbers; ``:a`` ``aa``, ``~ab``
    ``ba``, ``!a`` nothing, ``(a`` ``[a]`` on any value; ``$ab`` ``a`` copies
    of ``b`` for a number ``a``; ``<[x]b`` ``[xb]``; ``)[x]`` ``x``; ``H``.

Input/output:
    A read takes one character's code point; a read at EOF halts.
    Printing writes the number as a character.

Errors:
    ProgramError: A character outside the syntax; an unmatched bracket.
    HaltError: Printing a number that is no code point; ``/`` by 0; ``$``
        with a negative count.

Decisions:
    * Results are pushed in their written order, ``~ab`` pushing ``b`` then
      ``a``: the other order would push what moving ``a`` and ``b`` does,
      making ``~`` a no-op.  So a pass's output is read reversed next pass.
    * Functions and blocks are values: ``::`` loops only if ``:``
      duplicates a function.
    * Every pair of consecutive quiet swaps reads, including one that
      follows a read: the page names no reset.  The first swap never reads.
    * ``/`` floors; dividing by 0 or copying a negative count raises, since
      the page gives no result.
    * A read at EOF halts: the page's cat "doesn't handle end of file", so
      a program has no EOF test, and pairwise reads drop an odd last
      character.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import cast

from esolangs.exceptions import HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime.io import IO

_FUNCTIONS = frozenset("+-*/%:~!$(<)H")
_NUMERIC = {"+": 2, "-": 1, "*": 2, "/": 2, "%": 1}
_ANY = {":": 1, "~": 2, "!": 1, "(": 1}

#: A number, a function's character, or a block.
type _Value = int | str | Block
#: A persistent stack, top first: ``(top, rest)`` cells ending in ``None``.
type _Stack = tuple[_Value, _Stack] | None
#: ``(forward, backward, active since the last swap, swapped yet, halted)``.
type _State = tuple[_Stack, _Stack, bool, bool, bool]


@dataclass(frozen=True, slots=True)
class Block:
    """A block's contents, last first, so ``<`` appends in O(1)."""

    rest: _Stack = None

    def items(self) -> list[_Value]:
        """The contents in written order."""
        out: list[_Value] = []
        cell = self.rest
        while cell is not None:
            out.append(cell[0])
            cell = cell[1]
        return out[::-1]


def parse(code: str) -> _Stack:
    """Return the forward stack; bad syntax raises ``ValueError``."""
    levels: list[list[_Value]] = [[]]
    i = 0
    while i < len(code):
        c = code[i]
        if c.isdigit() and c.isascii():
            j = i
            while j < len(code) and code[j].isdigit() and code[j].isascii():
                j += 1
            levels[-1].append(int(code[i:j]))
            i = j
            continue
        if c == "[":
            levels.append([])
        elif c == "]":
            if len(levels) == 1:
                raise ValueError(f"Fackward: unmatched ']' at offset {i}")
            items = levels.pop()
            levels[-1].append(Block(_push_all(None, items)))
        elif c in _FUNCTIONS:
            levels[-1].append(c)
        elif not c.isspace():
            raise ValueError(f"Fackward: {c!r} at offset {i} is not Fackward")
        i += 1
    if len(levels) > 1:
        raise ValueError("Fackward: unmatched '['")
    return _push_all(None, levels[0][::-1])


def _push_all(stack: _Stack, values: list[_Value]) -> _Stack:
    """Push ``values`` in order, the last ending on top."""
    for value in values:
        stack = (value, stack)
    return stack


def _take(stack: _Stack, count: int) -> list[_Value] | None:
    """The top ``count`` values, or ``None`` if the stack is shorter."""
    out: list[_Value] = []
    while len(out) < count:
        if stack is None:
            return None
        out.append(stack[0])
        stack = stack[1]
    return out


def _flat(stack: _Stack) -> tuple[_Value, ...]:
    """The stack's values, top first."""
    out = []
    while stack is not None:
        out.append(stack[0])
        stack = stack[1]
    return tuple(out)


def _drop(stack: _Stack, count: int) -> _Stack:
    for _ in range(count):
        assert stack is not None
        stack = stack[1]
    return stack


def _arguments(name: str, forward: _Stack) -> list[_Value] | None:
    """The values ``name`` would consume from ``forward``, or ``None``."""
    if name in _NUMERIC:
        args = _take(forward, _NUMERIC[name])
        ok = args is not None and all(type(a) is int for a in args)
    elif name in _ANY:
        args = _take(forward, _ANY[name])
        ok = args is not None
    else:
        args = _take(forward, {"$": 2, "<": 2, ")": 1, "H": 0}[name])
        ok = args is not None and (
            (name == "$" and type(args[0]) is int)
            or (name in "<)" and isinstance(args[0], Block))
            or name == "H"
        )
    return args if ok else None


def _apply(name: str, args: list[_Value]) -> list[_Value]:
    """Return the results of ``name`` on ``args``, in written order."""
    if name in _NUMERIC:
        a, *more = cast(list[int], args)
        if name == "+":
            return [a + more[0]]
        if name == "-":
            return [-a]
        if name == "*":
            return [a * more[0]]
        if name == "/":
            if more[0] == 0:
                raise HaltError(f"Fackward: / of {a} by 0")
            return [a // more[0]]
        return [int(a == 0)]
    if name == ":":
        return [args[0], args[0]]
    if name == "~":
        return [args[1], args[0]]
    if name == "!":
        return []
    if name == "(":
        return [Block((args[0], None))]
    if name == "$":
        count = cast(int, args[0])
        if count < 0:
            raise HaltError(f"Fackward: $ with the negative count {count}")
        return [args[1]] * count
    block = cast(Block, args[0])
    if name == "<":
        return [Block((args[1], block.rest))]
    return block.items()  # ")"


def reads_next(state: _State) -> bool:
    """Report whether the next step is a swap that reads a character."""
    forward, _backward, active, swapped, halted = state
    return not halted and forward is None and swapped and not active


def _advance(state: _State, value: int | None = None) -> tuple[_State, str | None]:
    """Return the state after one step, and the text it prints.

    Pure: the code point a reading swap takes arrives as ``value``.
    """
    forward, backward, active, swapped, _halted = state
    if forward is None:
        if reads_next(state):
            assert value is not None
            return ((backward, (value, None), False, True, False)), None
        return (backward, None, False, True, False), None
    top, rest = forward
    if type(top) is int:
        if not (0 <= top <= sys.maxunicode and not 0xD800 <= top <= 0xDFFF):
            raise HaltError(f"Fackward: printing {top}, which is no code point")
        return (rest, backward, True, swapped, False), chr(top)
    if isinstance(top, str):
        args = _arguments(top, rest)
        if args is not None:
            if top == "H":
                return (rest, backward, True, swapped, True), None
            results = _apply(top, args)
            rest = _drop(rest, len(args))
            return (rest, _push_all(backward, results), True, swapped, False), None
    return (rest, (top, backward), active, swapped, False), None


class _Machine:
    """The run state: both stacks and the quiet-swap bookkeeping."""

    ip_shape = "opaque"

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.state: _State = (parse(code), None, False, False, False)

    @property
    def halted(self) -> bool:
        return self.state[4]

    @property
    def ip(self) -> tuple[int, int]:
        """The forward and backward stack depths."""
        return (_depth(self.state[0]), _depth(self.state[1]))

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection.

        The stacks go out flat: comparing ``(top, rest)`` cells recurses once
        a cell, and a 930-deep stack overflowed it.
        """
        forward, backward, *flags = self.state
        return (_flat(forward), _flat(backward), *flags, self.io.progress())

    def step(self) -> None:
        """Run one step, reading first when it is a reading swap."""
        if self.halted:
            return
        value = None
        if reads_next(self.state):
            try:
                value = self.io.input_char()
            except EOFError:
                self.state = (*self.state[:4], True)
                return
        self.state, out = _advance(self.state, value)
        if out is not None:
            self.io.print_str(out)


def _depth(stack: _Stack) -> int:
    depth = 0
    while stack is not None:
        depth += 1
        stack = stack[1]
    return depth


def run(code: str, io: IO) -> None:
    """Run a Fackward program."""
    drive(_Machine(code, io))


if __name__ == "__main__":
    script_main(run)
