"""Interpreter for Pointless.

A tape of wrapping bytes, unbounded to the right, and a pointer at cell 0.
Most commands go through the current cell's value ``v`` as an address:
``=``, ``+`` and ``-`` set, add or subtract ``tape[v]``; ``:`` moves the
pointer to ``v``; ``[`` skips past its ``]`` when ``tape[v]`` is 0 and
``]`` jumps back when it is not.  ``"name"`` calls a function and
``"name"{...}`` declares one, anywhere; any other character is a comment.
The program halts at its end.  The wiki's Hello world runs as stated.

Commands:
    ``< >``: move the pointer.
    ``!``: increment the current cell; it may run once per run.
    ``.``: print the current cell as a character.
    ``,``: read a character into the current cell.

Input/output:
    ``,`` stores a character's code point modulo 256; ``.`` writes the
    character with the cell's value.

Errors:
    ProgramError: An unmatched bracket or brace; an unterminated quote; a
        call to an undeclared function; a duplicate declaration.
    InputExhaustedError: ``,`` at EOF.
    HaltError: Moving left of cell 0; a second ``!``.

Decisions:
    * Declarations are hoisted and global, may nest, and are skipped where
      they stand; a call runs the body and returns.
    * Brackets match within the main program or one function body.
    * ``"name"`` is a declaration when the next character that is no
      comment is ``{``, as the wiki says; a command, a quote or a brace
      ends the comment run.
    * ``]`` jumps to just after its ``[``, testing ``tape[v]`` itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, NamedTuple

from esolangs.exceptions import HaltError
from esolangs.languages.pointless.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO

_COMMANDS = frozenset('<>:!=+-[].,"{}')

#: ``(source offset, command)``; a call's command is the function's name
#: prefixed by ``"``.
type _Op = tuple[int, str]
#: ``(ops, matching bracket by op index)`` for one body.
type _Body = tuple[tuple[_Op, ...], Mapping[int, int]]
#: ``(body, next op)`` frames, innermost first.
type _Frames = tuple[tuple[int, int], _Frames] | None


class _Image(NamedTuple):
    end: int
    bodies: tuple[_Body, ...]
    names: Mapping[str, int]


def _parse(code: str) -> _Image:
    """Retain the source extent, parsed bodies and name lookup."""
    raw: list[list[_Op]] = [[]]
    open_bodies = [0]
    names: dict[str, int] = {}
    pos = 0
    while pos < len(code):
        char = code[pos]
        if char == '"':
            end = code.find('"', pos + 1)
            if end < 0:
                raise ValueError(f"Pointless: unterminated quote at {pos}")
            name = code[pos + 1 : end]
            after = end + 1
            while after < len(code) and code[after] not in _COMMANDS:
                after += 1
            if after < len(code) and code[after] == "{":
                if name in names:
                    raise ValueError(f"Pointless: {name!r} is declared twice")
                names[name] = len(raw)
                raw.append([])
                open_bodies.append(names[name])
                pos = after + 1
                continue
            raw[open_bodies[-1]].append((pos, '"' + name))
            pos = end + 1
            continue
        if char == "{":
            raise ValueError(f"Pointless: '{{' at {pos} follows no function name")
        if char == "}":
            if len(open_bodies) == 1:
                raise ValueError(f"Pointless: unmatched '}}' at {pos}")
            open_bodies.pop()
        elif char in _COMMANDS:
            raw[open_bodies[-1]].append((pos, char))
        pos += 1
    if len(open_bodies) > 1:
        raise ValueError("Pointless: a function body has no '}'")
    bodies: list[_Body] = []
    for ops in raw:
        jumps: dict[int, int] = {}
        opens: list[int] = []
        for k, (offset, op) in enumerate(ops):
            if op == "[":
                opens.append(k)
            elif op == "]":
                if not opens:
                    raise ValueError(f"Pointless: unmatched ']' at {offset}")
                jumps[k] = opens.pop()
                jumps[jumps[k]] = k
            elif op[0] == '"' and op[1:] not in names:
                raise ValueError(f"Pointless: {op[1:]!r} is never declared")
        if opens:
            raise ValueError(f"Pointless: unmatched '[' at {ops[opens[-1]][0]}")
        bodies.append((tuple(ops), MappingProxyType(jumps)))
    return _Image(len(code), tuple(bodies), MappingProxyType(names))


def _advance(
    frames: _Frames,
    bodies: tuple[_Body, ...],
    names: Mapping[str, int],
    pointer: int,
    cell: int,
    target: int,
    *,
    banged: bool,
    byte: int | None = None,
) -> tuple[_Frames, int, int | None, str | None, bool]:
    """Run one command: frames, pointer, the cell's new value, output, ``!`` used.

    Pure: ``cell`` is the current cell, ``target`` the cell its value names;
    a read arrives as ``byte``.
    """
    assert frames is not None
    (body, pc), rest = frames
    ops, jumps = bodies[body]
    op = ops[pc][1]
    frames = ((body, pc + 1), rest)
    write: int | None = None
    out = None
    if op[0] == '"':
        frames = ((names[op[1:]], 0), frames)
    elif op == "<":
        if pointer == 0:
            raise HaltError("Pointless moved left of cell 0")
        pointer -= 1
    elif op == ">":
        pointer += 1
    elif op == ":":
        pointer = cell
    elif op == "!":
        if banged:
            raise HaltError("Pointless ran '!' a second time")
        write, banged = (cell + 1) % 256, True
    elif op == "=":
        write = target
    elif op == "+":
        write = (cell + target) % 256
    elif op == "-":
        write = (cell - target) % 256
    elif op == "[":
        if not target:
            frames = ((body, jumps[pc] + 1), rest)
    elif op == "]":
        if target:
            frames = ((body, jumps[pc] + 1), rest)
    elif op == ".":
        out = chr(cell)
    else:
        assert byte is not None
        write = byte % 256
    while frames is not None and frames[0][1] >= len(bodies[frames[0][0]][0]):
        frames = frames[1]
    return frames, pointer, write, out, banged


_WORKSPACE_MODEL = WorkspaceModel(
    "pointless-v1", ("frames", "pointer", "tape", "banged", "input_cursor")
)


class _Machine:
    """The shell around :func:`_advance`: the tape, input and output."""

    def __init__(self, code: str | _Image, io: IO) -> None:
        self.io = io
        image = _parse(code) if isinstance(code, str) else code
        self.end, self.bodies, self.names = image
        self.frames: _Frames = ((0, 0), None) if self.bodies[0][0] else None
        self.tape = bytearray(1)
        self.pointer = 0
        self.banged = False

    @property
    def halted(self) -> bool:
        return self.frames is None

    @property
    def ip(self) -> int:
        """The next command's source offset; the code's length once halted."""
        if self.frames is None:
            return self.end
        body, pc = self.frames[0]
        return self.bodies[body][0][pc][0]

    @property
    def memory(self) -> list[int]:
        """The tape cells written so far."""
        return list(self.tape)

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        frames = []
        rest = self.frames
        while rest is not None:
            frame, rest = rest
            frames.append(frame)
        return _WORKSPACE_MODEL.capture(
            frames=tuple(frames),
            pointer=self.pointer,
            tape=bytes(self.tape).rstrip(b"\0"),
            banged=self.banged,
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        return (
            self.frames,
            self.pointer,
            bytes(self.tape).rstrip(b"\0"),
            self.banged,
            self.io.progress(),
        )

    def _cell(self, address: int) -> int:
        return self.tape[address] if address < len(self.tape) else 0

    def step(self) -> None:
        """Run one command, reading input first when it is ``,``."""
        if self.frames is None:
            return
        body, pc = self.frames[0]
        op = self.bodies[body][0][pc][1]
        byte = self.io.input_char() if op == "," else None
        cell = self._cell(self.pointer)
        self.frames, pointer, write, out, self.banged = _advance(
            self.frames,
            self.bodies,
            self.names,
            self.pointer,
            cell,
            self._cell(cell),
            banged=self.banged,
            byte=byte,
        )
        if write is not None:
            if self.pointer >= len(self.tape):
                self.tape.extend(bytes(self.pointer + 1 - len(self.tape)))
            self.tape[self.pointer] = write
        self.pointer = pointer
        if out is not None:
            self.io.print_str(out)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Share parsed source across runs with fresh machine state."""
    if not isinstance(source, str):
        raise TypeError("pointless machines require text source")
    if options:
        raise TypeError("pointless machines accept no runtime options")

    image = _parse(source)

    def build(io: IO) -> _Machine:
        return _Machine(image, io)

    return RuntimePlan(build, lambda io: _execute(image, io))


def _execute(code: str | _Image, io: IO) -> CompletionReport:
    """Run a Pointless program."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Run a Pointless program."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
