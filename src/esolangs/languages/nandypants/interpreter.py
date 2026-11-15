r"""Nandypants: two bit tapes, a NAND write on each, and numbered jumps.

Tape a and tape b are unbounded in both directions and start all 0; ``a`` and
``b`` name the bits under their pointers.  Any digit run is a label, read as a
decimal number (``03`` is ``3``); every other non-command character is ignored
and ends a digit run, so a space separates adjacent labels.

Commands:
    { }   move tape a's pointer left / right
    < >   move tape b's pointer left / right
    ^ v   a := a NAND b / b := a NAND b
    \     append a to the output stream
    /     b := the next input bit
    even  not the first occurrence of the number and a NAND b == 0: jump back
          to its first occurrence
    odd   not the last occurrence and a NAND b == 1: jump to its last occurrence

Input/output:
    Bits move least-significant first, eight to a byte; Unicode input is
    reduced modulo 256.  A partial output byte is padded with zero bits at halt.
    A read past the end of input raises EOFError.

Errors:
    InputExhaustedError: ``/`` with no input bit left; raised as EOFError.

Decisions:
    * Occurrences are counted over the whole source, by number.  A jump lands
      on the occurrence, which is then a no-op (first for even, last for odd),
      so landing on or after it is the same.
    * EOF is an error: the page's cat program "does not handle EOF" and so
      runs until it reads past the end of its input.
    * Bytes, LSB-first packing and the padded final byte follow Boolfuck, the
      language the page translates from; the page fixes none of them.
"""

import re
from collections.abc import Mapping
from typing import Any, NamedTuple

from esolangs.languages.nandypants.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.bits import flush_byte, put_bit, take_bit
from esolangs.runtime.io import IO, _BufferedOutput
from esolangs.runtime.memory import parse_integer

_TOKEN = re.compile(r"\d+|[{}<>^v\\/]")


class _State(NamedTuple):
    pc: int  # index into the token list
    a_ptr: int
    b_ptr: int
    incoming: int  # buffered input byte
    remaining: int  # input bits left in it
    outgoing: int  # output byte under construction
    used: int  # its filled bits


class _Program(NamedTuple):
    tokens: tuple[str, ...]
    first: dict[int, int]  # label number -> token index of its first occurrence
    last: dict[int, int]


def _parse(code: str) -> _Program:
    tokens = tuple(_TOKEN.findall(code))
    first: dict[int, int] = {}
    last: dict[int, int] = {}
    for index, token in enumerate(tokens):
        if token.isdigit():
            number = parse_integer(token)
            first.setdefault(number, index)
            last[number] = index
    return _Program(tokens, first, last)


def _advance(state: _State, token: str, nand: int, program: _Program) -> _State:
    """Advance control and pointers; tape writes and byte I/O are shell effects."""
    pc = state.pc + 1
    if token == "{":
        return _State(
            pc,
            state.a_ptr - 1,
            state.b_ptr,
            state.incoming,
            state.remaining,
            state.outgoing,
            state.used,
        )
    if token == "}":
        return _State(
            pc,
            state.a_ptr + 1,
            state.b_ptr,
            state.incoming,
            state.remaining,
            state.outgoing,
            state.used,
        )
    if token == "<":
        return _State(
            pc,
            state.a_ptr,
            state.b_ptr - 1,
            state.incoming,
            state.remaining,
            state.outgoing,
            state.used,
        )
    if token == ">":
        return _State(
            pc,
            state.a_ptr,
            state.b_ptr + 1,
            state.incoming,
            state.remaining,
            state.outgoing,
            state.used,
        )
    if token.isdigit():
        number = parse_integer(token)
        if number % 2 == 0:
            if state.pc != program.first[number] and nand == 0:
                pc = program.first[number]
        elif state.pc != program.last[number] and nand == 1:
            pc = program.last[number]
    return _State(
        pc,
        state.a_ptr,
        state.b_ptr,
        state.incoming,
        state.remaining,
        state.outgoing,
        state.used,
    )


def _set(tape: set[int], ptr: int, bit: int) -> None:
    if bit:
        tape.add(ptr)
    else:
        tape.discard(ptr)


_WORKSPACE_MODEL = WorkspaceModel(
    "nandypants-v1", ("control", "first_tape", "second_tape", "input_cursor")
)


_Image = tuple[str, _Program]


def _prepare_source(code: str) -> _Image:
    return code, _parse(code)


class _Machine:
    """Two sparse bit tapes and buffered byte streams."""

    ip_shape = "opaque"  # pc indexes tokens, not source characters

    def __init__(self, code: str | _Image, io: IO) -> None:
        self.io = io
        image = _prepare_source(code) if isinstance(code, str) else code
        self.code, self.program = image
        self.state = _State(0, 0, 0, 0, 0, 0, 0)
        self.a_ones: set[int] = set()
        self.b_ones: set[int] = set()
        self._writer = _BufferedOutput()
        self._pending_output: tuple[_State, int] | None = None

    @property
    def halted(self) -> bool:
        return self.state.pc >= len(self.program.tokens)

    @property
    def ip(self) -> int:
        return self.state.pc

    @property
    def ptr(self) -> int:
        return self.state.a_ptr

    @property
    def memory(self) -> list[int]:
        ones = self.a_ones | {self.state.a_ptr, 0}
        return [int(i in self.a_ones) for i in range(min(ones), max(ones) + 1)]

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Capture logical workspace independently of cycle keys and backing storage."""
        control = tuple(self.state)
        pending = self._output_boundary()
        return _WORKSPACE_MODEL.capture(
            control=WorkspaceVariant("pending_output", (control, *pending))
            if pending is not None
            else control,
            first_tape=frozenset(self.a_ones),
            second_tape=frozenset(self.b_ones),
            input_cursor=self.io.progress(),
        )

    def snapshot(self) -> tuple[object, ...]:
        boundary = (
            self.state,
            frozenset(self.a_ones),
            frozenset(self.b_ones),
            self.io.progress(),
        )
        pending = self._output_boundary()
        return (*boundary, pending) if pending is not None else boundary

    def _output_boundary(self) -> tuple[_State, int, int] | None:
        if self._pending_output is None:
            return None
        return (*self._pending_output, self._writer.accepted or 0)

    def _write_byte(self, state: _State, byte: int) -> None:
        char = chr(byte)
        try:
            self._writer.write(self.io, char, first=lambda: self.io.print_char(char))
        except BaseException:
            # Terminal padding can follow a read or tape edit in this command.
            self._pending_output = state, byte
            raise
        self.state = state
        self._pending_output = None

    def step(self) -> None:
        if self.halted:
            return
        if self._pending_output is not None:
            self._write_byte(*self._pending_output)
            return
        state = self.state
        token = self.program.tokens[state.pc]
        a = int(state.a_ptr in self.a_ones)
        b = int(state.b_ptr in self.b_ones)
        nand = 1 - (a & b)
        full = None
        if token == "^":
            _set(self.a_ones, state.a_ptr, nand)
        elif token == "v":
            _set(self.b_ones, state.b_ptr, nand)
        elif token == "/":
            incoming, remaining = state.incoming, state.remaining
            if not remaining:
                incoming, remaining = self.io.input_char() % 256, 8
            (incoming, remaining), bit = take_bit((incoming, remaining))
            _set(self.b_ones, state.b_ptr, bit)
            state = _State(
                state.pc,
                state.a_ptr,
                state.b_ptr,
                incoming,
                remaining,
                state.outgoing,
                state.used,
            )
        elif token == "\\":
            (outgoing, used), full = put_bit((state.outgoing, state.used), a)
            state = _State(
                state.pc,
                state.a_ptr,
                state.b_ptr,
                state.incoming,
                state.remaining,
                outgoing,
                used,
            )
        state = _advance(state, token, nand, self.program)
        if state.pc >= len(self.program.tokens):
            if full is None:
                full = flush_byte((state.outgoing, state.used))
            state = _State(
                state.pc,
                state.a_ptr,
                state.b_ptr,
                state.incoming,
                state.remaining,
                0,
                0,
            )
        if full is None:
            self.state = state
        else:
            self._write_byte(state, full)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Parse source once and build fresh state for each run."""
    if not isinstance(source, str):
        raise TypeError("nandypants machines require text source")
    if options:
        raise TypeError("nandypants machines accept no runtime options")
    image = _prepare_source(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | _Image, io: IO) -> CompletionReport:
    """Execute Nandypants and flush its final partial byte."""
    return drive(_Machine(code, io), policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Execute Nandypants and flush its final partial byte."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run)
