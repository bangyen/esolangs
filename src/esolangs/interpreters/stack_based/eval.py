r"""Interpreter for Eval."""

from __future__ import annotations

import sys
from collections.abc import Hashable

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import IO

# : A value on a stack: Eval's.
type _Val = int | str

# : The part of a run the pure.
# : active stack index and both.
# : transition below returns a.
# :.
# : The code cursor is *not* in.
# : ``!`` gets its own, while.
type _Core = tuple[int, tuple[tuple[_Val, ...], tuple[_Val, ...]]]

# : One frame on the call.
# : A plain tuple, rebuilt.
#: the cycle detector can hash.
type _Frame = tuple[str, int]

# : Every value an Eval command.
# : immutable call-frame stack.
#: in the shell.
type _State = tuple[_Core, tuple[_Frame, ...]]


class _Fault(Exception):  # noqa: N818 - an internal signal, not an error type
    r"""Raised inside the pure layer for an invalid operation."""


def _pushed(core: _Core, value: _Val) -> _Core:
    r"""Return ``core`` with ``value`` pushed on the active stack."""
    ptr, stacks = core
    active = (*stacks[ptr], value)
    return (ptr, (active, stacks[1]) if ptr == 0 else (stacks[0], active))


def _popped(core: _Core) -> tuple[_Core, _Val]:
    r"""Return ``core`` without its top, and the value that was on top."""
    ptr, stacks = core
    if not stacks[ptr]:
        raise _Fault
    rest, value = stacks[ptr][:-1], stacks[ptr][-1]
    return (ptr, (rest, stacks[1]) if ptr == 0 else (stacks[0], rest)), value


def _iterate(
    core: _Core, sym: str, ind: int
) -> tuple[_Core, int, _Val | None, str | None]:
    r"""Execute one command, returning core, index, any output, any call."""
    ptr, stacks = core
    char = sym[ind]
    output: _Val | None = None
    call: str | None = None
    if char == "`":
        core = _pushed(core, 1 - ptr)
    elif char == "^":
        if not stacks[ptr]:
            raise _Fault
        core = _pushed(core, stacks[ptr][-1])
    elif char == "0":
        core = _pushed(core, 0)
    elif char in "+-":
        core, value = _popped(core)
        if not isinstance(value, int):
            raise _Fault
        core = _pushed(core, value + (1 if char == "+" else -1))
    elif char == ".":
        core, output = _popped(core)
    elif char == "=":
        core, value = _popped(core)
        ptr, stacks = core
        other = (*stacks[1 - ptr], value)
        core = (ptr, (stacks[0], other) if ptr == 0 else (other, stacks[1]))
    elif char == ";":
        core, _value = _popped(core)
    elif char == "~":
        core = (ptr ^ 1, stacks)
    elif char == "*":
        reversed_ = stacks[ptr][::-1]
        core = (ptr, (reversed_, stacks[1]) if ptr == 0 else (stacks[0], reversed_))
    elif char == "?":
        core, value = _popped(core)
        if not value:
            ind += 1
    elif char == "!":
        core, value = _popped(core)
        if not isinstance(value, str):
            raise _Fault
        call = value
    elif char in "\"'":
        # A literal runs to the next.
        # when there is none -- which.
        # way, with no unmatched case.
        text = sym[ind + 1 :].partition('"')[0].replace("`", '"')
        ind += len(text) + 1
        core = _pushed(core, f'"{text}"' if char == "'" else text)
    return core, ind + 1, output, call


class _Machine:
    r"""Two stacks with an index choosing the active one, and a frame stack."""

    ptr: int
    stk: tuple[tuple[_Val, ...], tuple[_Val, ...]]
    io: IO
    sym: str
    frames: tuple[_Frame, ...]

    def __init__(self, code: str, io: IO) -> None:
        r"""Build a state running ``code``."""
        self.ptr = 0
        self.stk = ((), ())
        self.io = io
        self.sym = code
        self.frames = ((code, 0),) if code else ()

    @property
    def ind(self) -> int:
        r"""The innermost frame's cursor."""
        return self.frames[-1][1] if self.frames else len(self.sym)

    @property
    def halted(self) -> bool:
        r"""Whether every frame has returned."""
        return not self.frames

    # The VM's language-shaped.
    # ``stack`` is whichever one.
    # addressable cells.

    # : ``ip`` is a position, but.
    #: the innermost cursor.
    # : Declared rather than left.
    # : classified is a missing.
    ip_shape = "opaque"

    @property
    def ip(self) -> tuple[int, int]:
        r"""The call depth and the innermost frame's cursor."""
        return (len(self.frames), self.ind)

    @property
    def memory(self) -> list[int]:
        r"""No addressable cells; the store is the active stack."""
        return []

    @property
    def stack(self) -> list[int | str]:
        r"""The active stack, the one ``ptr`` currently selects."""
        return list(self.stk[self.ptr])

    def snapshot(self) -> tuple[object, ...]:
        r"""Return the complete internal state, hashable for cycle detection."""
        return (
            self.ptr,
            self.stk,
            tuple(self.frames),
            self.io.position(),
        )

    @property
    def _state(self) -> _State:
        r"""The complete changing state at the command boundary."""
        return ((self.ptr, self.stk), self.frames)

    def _restore(self, state: _State) -> None:
        r"""Write a pure command transition back onto the machine shell."""
        (self.ptr, self.stk), self.frames = state

    def frame_entry_key(self, frame: _Frame) -> Hashable:
        r"""Return what ``frame`` is about to run, for the ancestor check."""
        sym, ind = frame
        return (
            sym,
            ind,
            self.ptr,
            self.stk,
            self.io.position(),
        )

    def step(self) -> None:
        r"""Execute one command of the innermost frame."""
        core, frames = self._state
        if not frames:
            return
        sym, ind = frames[-1]
        if ind >= len(sym):
            self._restore((core, frames[:-1]))
            return
        try:
            core, ind, output, call = _iterate(core, sym, ind)
        except _Fault:
            raise HaltError from None
        if output is not None:
            self.io.print_value(output)
        frames = (*frames[:-1], (sym, ind))
        if call is not None:
            # The nested program becomes a.
            # running here, which is what.
            frames = (*frames, (call, 0))
        self._restore((core, frames))


def run(code: str, io: IO) -> None:
    r"""Run an Eval program."""
    state = _Machine(code, io)
    while not state.halted:
        state.step()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as file:
            data = file.read()
            run(data, IO())
