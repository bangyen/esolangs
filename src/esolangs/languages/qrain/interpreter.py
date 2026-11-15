"""Interpreter for Qrain (esolangs.org oldid 198382).

A two-sided tape of unbounded bit queues and one output bit queue.  Any
character that is not a command is ignored.

Commands:
    ``>`` ``<``  move to the next queue right or left.
    ``+``        enqueue 1 on the current queue if its front bit equals the
                 output queue's front bit, else 0.
    ``-``        dequeue the current queue's front bit.
    ``.``        move up to eight bits from the front of the current queue to
                 the back of the output queue; if that holds eight or more
                 bits, dequeue eight and print them as a byte.
    ``,``        enqueue a byte's eight bits, low bit first.
    ``[`` ``]``  skip past the matching ``]`` when the front bit is 0; jump
                 back after the matching ``[`` when it is 1.

Input/output:
    Bits move least-significant first.  A read at EOF supplies byte 0.  Bits
    in the output queue short of a byte are never printed.

Errors:
    ProgramError: unmatched brackets.
    HaltError: ``-`` on an empty queue.

Decisions:
    * An empty queue's front reads 0 (``+``, ``[``, ``]``); only ``-`` raises,
      as the page says.  ``.`` on an empty queue moves zero bits, "up to
      eight" allowing none.
    * The page's ``]`` sentence lost its "if"; read as the mirror of ``[``.
    * One ``.`` prints at most one byte: it adds at most eight bits to an
      output queue holding at most seven.
    * The tape grows left as well as right, with no clamp.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from itertools import islice
from types import MappingProxyType
from typing import Any, NamedTuple

from esolangs.exceptions import HaltError
from esolangs.languages.qrain.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._snapshot import named_tuple_codec
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.brackets import match_brackets
from esolangs.runtime.io import IO, ScriptedIO, _BufferedOutput


class _State(NamedTuple):
    pc: int
    ptr: int


SNAPSHOT_CODECS = (named_tuple_codec(_State, _State._make),)


def _advance(
    state: _State, command: str, front: int, brackets: Mapping[int, int]
) -> _State:
    """Advance control; the queues are shell effects."""
    pc, ptr = state
    if command == ">":
        ptr += 1
    elif command == "<":
        ptr -= 1
    elif (command == "[" and not front) or (command == "]" and front):
        pc = brackets[pc]
    # Skip the Python constructor wrapper.
    # [interpreter_ablations.speedup_adoption_20261103]
    return tuple.__new__(_State, (pc + 1, ptr))


_WORKSPACE_MODEL = WorkspaceModel(
    "qrain-v1", ("control", "queues", "output_bits", "input_cursor")
)


type _SourceImage = tuple[str, Mapping[int, int]]


def _prepare_source(code: str) -> _SourceImage:
    return code, MappingProxyType(match_brackets(code))


class _Machine:
    """The bit-queue tape and the output bit queue."""

    eof_is_a_value = True

    def __init__(self, code: str | _SourceImage, io: IO) -> None:
        self.code, self.brackets = (
            _prepare_source(code) if isinstance(code, str) else code
        )
        self.io = io
        self.state = tuple.__new__(_State, (0, 0))
        self.queues: dict[int, deque[int]] = {}
        self.out: deque[int] = deque()
        self._writer = _BufferedOutput()

    @property
    def halted(self) -> bool:
        return self.state.pc >= len(self.code)

    @property
    def ip(self) -> int:
        return self.state.pc

    @property
    def ptr(self) -> int:
        return self.state.ptr

    @property
    def memory(self) -> list[int]:
        """The front bit of each queue from the leftmost used one to the pointer."""
        cells = {*self.queues, self.state.ptr, 0}
        return [
            self.queues[i][0] if self.queues.get(i) else 0
            for i in range(min(cells), max(cells) + 1)
        ]

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture semantic components independently of storage and cycle grouping."""
        accepted = self._writer.accepted
        control = (self.state.pc, self.state.ptr)
        return _WORKSPACE_MODEL.capture(
            control=(
                control
                if not accepted
                else WorkspaceVariant("pending_output", (*control, accepted))
            ),
            queues=frozenset((i, tuple(q)) for i, q in self.queues.items() if q),
            output_bits=tuple(self.out),
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        queues = tuple(sorted((i, tuple(q)) for i, q in self.queues.items() if q))
        boundary = (self.state, queues, tuple(self.out), self.io.progress())
        accepted = self._writer.accepted
        return (*boundary, accepted) if accepted else boundary

    def _transfer(self, queue: deque[int]) -> None:
        moved = min(8, len(queue))
        if len(self.out) + moved < 8:
            self.out.extend(queue.popleft() for _ in range(moved))
            return

        # Keep both queues intact until the byte has been written.
        bits = (*self.out, *islice(queue, moved))
        char = chr(sum(bit << i for i, bit in enumerate(bits[:8])))
        if isinstance(self.io, ScriptedIO):
            self._writer.write(self.io, char, first=lambda: self.io.print_char(char))
        else:
            self.io.print_char(char)
        for _ in range(moved):
            queue.popleft()
        self.out.clear()
        self.out.extend(bits[8:])

    def step(self) -> None:
        if self.halted:
            return
        pc, ptr = self.state
        command = self.code[pc]
        queue = self.queues.setdefault(ptr, deque())
        front = queue[0] if queue else 0
        if command == "+":
            queue.append(int(front == (self.out[0] if self.out else 0)))
        elif command == "-":
            if not queue:
                raise HaltError(
                    "'-' on an empty queue",
                    hint="enqueue a bit with '+' or ',' before dequeuing",
                )
            queue.popleft()
        elif command == ".":
            self._transfer(queue)
        elif command == ",":
            try:
                byte = self.io.input_char() % 256
            except EOFError:
                byte = 0
            queue.extend((byte >> i) & 1 for i in range(8))
        self.state = _advance(self.state, command, front, self.brackets)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Retain source and jump targets with fresh invocation state."""
    if not isinstance(source, str):
        raise TypeError("qrain machines require text source")
    if options:
        raise TypeError("qrain machines accept no runtime options")

    image = _prepare_source(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | _SourceImage, io: IO) -> CompletionReport:
    """Execute Qrain."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Execute Qrain."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
