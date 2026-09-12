r"""Interpreter for Forþ."""

import sys
from dataclasses import dataclass

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO


def _wrap32(value: int) -> int:
    r"""Wrap ``value`` to a signed 32-bit integer (C++ ``int`` arithmetic)."""
    return (value + 2**31) % 2**32 - 2**31


def _trunc_div(a: int, b: int) -> int:
    r"""C++-style integer division, truncating toward zero."""
    return int(a / b)


def _trunc_mod(a: int, b: int) -> int:
    r"""C++-style remainder (the sign of the dividend)."""
    return a - _trunc_div(a, b) * b


@dataclass(frozen=True)
class _Frame:
    r"""One active scope: its code, cursor, and whether it is a ``[`` loop."""

    code: str
    pc: int = 0
    loop: bool = False


# : One instant of a run:.
# : operand stack, the scope.
# : stack, and whether the.
# :.
# : The frames are the reason.
# : and all three bracket forms.
# : whenever it finishes with a.
# : because a called scope runs.
# :.
# : ``error`` is state and not.
# : scope the way completing it.
# : mean the run failed.
type _Frames = tuple[_Frame, ...]
type _State = tuple[tuple[int, ...], dict[int, str], _Frames, bool]


def _top(stack: tuple[int, ...]) -> int:
    r"""Return the top of ``stack``, halting when there is none."""
    if not stack:
        raise HaltError("the stack is empty, so there is no top value to read")
    return stack[-1]


def _at(frame: _Frame, pc: int) -> _Frame:
    r"""Return ``frame`` with its cursor moved to ``pc``."""
    return _Frame(frame.code, pc, frame.loop)


def _finalize(state: _State) -> _State:
    r"""Pop completed frames, re-running a ``[`` body while its top holds."""
    stack, table, frames, error = state
    while frames and frames[-1].pc >= len(frames[-1].code):
        frame = frames[-1]
        if frame.loop and _top(stack) != 0:
            return (
                stack,
                table,
                (*frames[:-1], _Frame(frame.code, 0, loop=True)),
                error,
            )
        frames = frames[:-1]
    return (stack, table, frames, error)


def _abort(state: _State) -> _State:
    r"""End the innermost scope on an invalid operation (status 3)."""
    stack, table, frames, error = state
    top_level = len(frames) == 1
    frame = frames[-1]
    ended = (stack, table, (*frames[:-1], _at(frame, len(frame.code))), error)
    stack, table, frames, error = _finalize(ended)
    return (stack, table, frames, error or top_level)


def _scan(frame: _Frame, add: str, sub: str) -> tuple[str, int] | None:
    r"""Return a bracket's body and the cursor past it, or ``None`` if open."""
    start = frame.pc - 1
    pc = frame.pc
    match = 1
    while True:
        if pc >= len(frame.code):
            return None
        inner = frame.code[pc]
        pc += 1
        if inner == add:
            match += 1
        elif inner == sub:
            match -= 1
        # Tested after the advance, so.
        # closing bracket rather than.
        if match == 0:
            break
    return (frame.code[start + 1 : pc - 1], pc)


def _advance(state: _State, line: str | None = None) -> _State:
    r"""Return the state after executing one command of the active frame."""
    state = _finalize(state)
    stack, table, frames, error = state
    if not frames:
        return state
    frame = frames[-1]
    if frame.pc >= len(frame.code):
        return state  # a finished pass (an empty.

    char = frame.code[frame.pc]
    frames = (*frames[:-1], _at(frame, frame.pc + 1))
    frame = frames[-1]
    state = (stack, table, frames, error)

    if "0" <= char <= "9":
        return ((*stack, ord(char) - 48), table, frames, error)
    if "A" <= char <= "F":
        return ((*stack, ord(char) - 55), table, frames, error)
    if char == ":":
        return ((*stack, _top(stack)), table, frames, error)
    if char == "~":
        return ((*stack[:-1], ~_top(stack)), table, frames, error)
    if char == ".":
        # The print already happened in.
        _top(stack)
        return (stack[:-1], table, frames, error)
    if char == ",":
        read = tuple(ord(ch) & 0xFF for ch in (line or ""))
        return ((*stack, *read), table, frames, error)
    if char == ";":
        scope = table.get(_top(stack), "")
        return (stack[:-1], table, (*frames, _Frame(scope)), error)
    if char == "o":
        return (tuple(reversed(stack)), table, frames, error)
    if char == "c":
        if len(stack) < 3:
            return _abort(state)
        return ((*stack[:-3], *stack[-2:], stack[-3]), table, frames, error)
    if char in "([{":
        sub = ")" if char == "(" else "]" if char == "[" else "}"
        found = _scan(frame, char, sub)
        if found is None:
            # The scan walked to the end.
            # left the cursor there before.
            ended = (stack, table, (*frames[:-1], _at(frame, len(frame.code))), error)
            return _abort(ended)
        scope, pc = found
        frames = (*frames[:-1], _at(frame, pc))
        state = (stack, table, frames, error)
        if char == "(":
            if _top(stack):
                return (stack, table, (*frames, _Frame(scope)), error)
            return state
        if char == "[":
            if _top(stack):
                return (stack, table, (*frames, _Frame(scope, 0, loop=True)), error)
            return state
        return (stack, {**table, _top(stack): scope}, frames, error)
    if char in "+-*/%v":
        if len(stack) < 2:
            return _abort(state)
        two, one = stack[-1], stack[-2]
        rest = stack[:-2]
        # Both operands are consumed.
        # zero-divisor abort leaves the.
        popped = (rest, table, frames, error)
        if char == "+":
            return ((*rest, _wrap32(one + two)), table, frames, error)
        if char == "-":
            return ((*rest, _wrap32(one - two)), table, frames, error)
        if char == "*":
            return ((*rest, _wrap32(one * two)), table, frames, error)
        if char == "/":
            if two == 0:
                return _abort(popped)
            return ((*rest, _wrap32(_trunc_div(one, two))), table, frames, error)
        if char == "%":
            if two == 0:
                return _abort(popped)
            return ((*rest, _wrap32(_trunc_mod(one, two))), table, frames, error)
        # The arm admits only.
        # this is ``v``: the swap.
        return ((*rest, two, one), table, frames, error)
    return state


class _Machine:
    r"""Per-run Forþ state: the shared stack, scope table, and call stack."""

    def __init__(self, code: str, io: IO) -> None:
        r"""Start with the top-level ``code`` as the only frame."""
        self.io = io
        self.stack: tuple[int, ...] = ()
        self.table: dict[int, str] = {}
        self.frames: tuple[_Frame, ...] = (_Frame(code),)
        self.error = False  # the top-level scope aborted.
        # Where the top-level frame.
        # report a position after that.
        self._length = len(code)

    @property
    def halted(self) -> bool:
        r"""Whether every scope has completed."""
        return not self.frames

    # The VM's language-shaped.
    # no addressable cells.

    # : ``ip`` is a position, but.
    #: outermost first.
    # : Declared rather than left.
    # : classified is a missing.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, ...]:
        r"""Each live frame's pc, outermost first."""
        frames = self.frames
        return tuple(f.pc for f in frames) if frames else (self._length,)

    @property
    def memory(self) -> list[int]:
        r"""No addressable cells; the store is the stack."""
        return []

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            self.stack,
            frozenset(self.table.items()),
            tuple((f.code, f.pc, f.loop) for f in self.frames),
            self.io.position(),
        )

    def frame_entry_key(self, frame: _Frame) -> tuple[object, ...]:
        r"""Return the state a called scope needs to replay an ancestor."""
        return (
            frame.code,
            frame.loop,
            self.stack,
            frozenset(self.table.items()),
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        r"""The machine's fields as the value the transition works on."""
        return (self.stack, self.table, self.frames, self.error)

    def _restore(self, state: _State) -> None:
        r"""Write a transition's result back onto the machine's fields."""
        stack, table, frames, self.error = state
        self.stack = stack
        self.table = table
        self.frames = frames

    def step(self) -> None:
        r"""Execute one command of the active frame."""
        if self.halted:
            return
        state = _finalize(self._state)
        stack, _table, frames, _error = state
        char = ""
        if frames and frames[-1].pc < len(frames[-1].code):
            char = frames[-1].code[frames[-1].pc]

        # The cursor moves past the.
        # the original had already.
        # raised -- an empty stack, or.
        # the advance up front.
        # .
        # A bracket walks further than.
        # condition is tested, so a.
        # the whole body.
        stack, table, frames, error = state
        if frames and frames[-1].pc < len(frames[-1].code):
            frame = _at(frames[-1], frames[-1].pc + 1)
            if char in "([{":
                sub = ")" if char == "(" else "]" if char == "[" else "}"
                found = _scan(frame, char, sub)
                frame = _at(frame, found[1] if found else len(frame.code))
            frames = (*frames[:-1], frame)
        self._restore((stack, table, frames, error))

        line = None
        if char == ",":
            line = self.io.input_str()
        elif char == "." and stack:
            self.io.print_char(chr(stack[-1] & 0xFF))

        self._restore(_advance(state, line))


def run(code: str, io: IO) -> None:
    r"""Run a Forþ program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()
    if machine.error:
        raise HaltError("the top-level scope aborted, which Forþ reports as status 3")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            run(file.read(), IO())
