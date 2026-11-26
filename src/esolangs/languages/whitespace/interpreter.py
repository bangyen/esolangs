r"""Interpreter for Whitespace.

A stack machine written in space, tab and line feed alone; every other
character is ignored.  A command is an Instruction Modification Parameter
(IMP) -- ``[Space]`` stack, ``[Tab][Space]`` arithmetic, ``[Tab][Tab]`` heap,
``[Tab][LF]`` I/O, ``[LF]`` flow -- then its subcommand, then a number or label.
A number is a sign (space positive, tab negative), binary digits (space 0,
tab 1) and a line feed; a label is spaces and tabs ended by a line feed.  The
program runs from its first command until ``end``.

Commands:
    [S][S] n     push n
    [S][LF][S]   duplicate the top;  [S][LF][T] swap;  [S][LF][LF] discard
    [S][T][S] n  copy the nth item (0 is the top) onto the top
    [S][T][LF] n slide n items off below the top, keeping the top
    [T][S] +  -  *  /  %   pop ``b``, then ``a``, and push ``a op b``
    [T][T][S]    store: pop a value, then an address
    [T][T][T]    retrieve: pop an address, push its value (0 if unset)
    [T][LF] SS ST TS TT  print char, print number, read char, read number
    [LF][S] SS ST SL  mark, call, jump (each with a label)
    [LF][T] S T  jump if zero, jump if negative (each with a label)
    [LF][T][LF]  return from a call;  [LF][LF][LF]  end

Input/output:
    A read pops a heap address and stores the character code or the
    signed ASCII decimal integer on one whole line. A print pops a value;
    a character prints its Unicode code point (0..0x10FFFF). EOF propagates.

Errors:
    ProgramError: an empty program; one that ends inside a command; an
    unassigned subcommand.
    InputExhaustedError: a read at EOF.
    ArgumentError: a number read given a blank or non-integer line.
    HaltError: a pop from an empty stack; division or modulo by zero; a
    ``copy`` past the stack; a ``slide`` on an empty stack; a ``return``
    with no call; a jump to a label that is never marked; character output
    outside 0..0x10FFFF.

Decisions:
    * Division rounds down and the remainder takes the divisor's sign,
      matching canonical VM.hs (Integer div/mod).
    * ``slide`` keeps the top and drops at most the available items below
      it; negative counts drop none, matching canonical VM.hs (Slide/drop).
      The former error claim for sliding past the stack was false.
    * ``copy`` counts from 0 at the top, as the reference implementation does.
    * Duplicate marks use the first occurrence, matching VM.hs findLabel.
    * Conditional branches fault on undefined labels only when taken, as VM.hs does.
      Falling off code halts in this adapter.
    * The wiki's Cat, Hello and Truth-machine pages show a line break after
      each rendered line that is not a line feed: breaks are dropped and each
      glyph read as its character.
    * Canonical reference: https://github.com/wspace/whitespace-haskell,
      VM.hs. Character output uses its Char range, including surrogate code
      points in buffered output; encoding belongs to the output sink. Values
      outside that range halt instead of reproducing host Int narrowing.
      Numeric reads consume a line, matching getLine; signed ASCII decimal
      syntax is retained rather than Haskell's full Read Integer grammar.
    * The heap deliberately accepts all integer addresses: absent cells read
      as zero, and zero stores erase sparse entries. VM.hs uses a finite list;
      its out-of-range read errors, host index narrowing and negative-store
      divergence are not reproduced. Workspace counts the sparse pairs.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from operator import floordiv, mod
from typing import Any

from esolangs.exceptions import ArgumentError, HaltError, ProgramError
from esolangs.languages.whitespace.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import RuntimePlan
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._source import text_source
from esolangs.runtime._state import (
    WorkspaceModel,
    WorkspaceSnapshot,
    WorkspaceVariant,
)
from esolangs.runtime._validate import require_text_source
from esolangs.runtime.io import IO, ScriptedIO, _BufferedOutput
from esolangs.runtime.memory import format_integer, parse_integer
from esolangs.runtime.source_hints import syntax_error

_SPACE, _TAB, _LINE = " ", "\t", "\n"
_EMPTY_STACK = "the stack is empty, so there is no top to pop"
type _Instruction = tuple[str, int | str]
type _Heap = tuple[tuple[int, int], ...]
type _State = tuple[int, tuple[int, ...], _Heap, tuple[int, ...], bool]

_WORKSPACE_MODEL = WorkspaceModel(
    "whitespace-v1",
    ("instruction", "stack", "heap", "return_stack", "ended", "input_cursor"),
)

_IO_KINDS = {
    (_SPACE, _SPACE): "out_char",
    (_SPACE, _TAB): "out_num",
    (_TAB, _SPACE): "read_char",
    (_TAB, _TAB): "read_num",
}
_ARITHMETIC = {
    (_SPACE, _SPACE): "add",
    (_SPACE, _TAB): "sub",
    (_SPACE, _LINE): "mul",
    (_TAB, _SPACE): "div",
    (_TAB, _TAB): "mod",
}
_STACK = {_SPACE: "dup", _TAB: "swap", _LINE: "discard"}
_LABELLED = {(_SPACE, _SPACE): "mark", (_SPACE, _TAB): "call", (_SPACE, _LINE): "jump"}
_BRANCH = {_SPACE: "jz", _TAB: "jn"}


_OPERATIONS: dict[str, Callable[[int, int], int]] = {
    "add": lambda left, right: left + right,
    "sub": lambda left, right: left - right,
    "mul": lambda left, right: left * right,
    "div": floordiv,
    "mod": mod,
}


def _parse(code: str) -> tuple[list[_Instruction], list[int]]:
    """Return the instruction stream and each instruction's source offset."""
    tokens = [(index, char) for index, char in enumerate(code) if char in "\t\n "]
    cursor = 0
    count = len(tokens)

    def take() -> str:
        nonlocal cursor
        if cursor >= count:
            raise ProgramError("Whitespace program ends inside an instruction")
        char = tokens[cursor][1]
        cursor += 1
        return char

    def number() -> int:
        negative = take() == _TAB
        value = 0
        while (bit := take()) != _LINE:
            value = value * 2 + (bit == _TAB)
        return -value if negative else value

    def label() -> str:
        chars = []
        while (char := take()) != _LINE:
            chars.append(char)
        return "".join(chars)

    def choose(options: Mapping[Any, str], key: object) -> str:
        try:
            return options[key]
        except KeyError:
            raise ProgramError(f"Whitespace has no command at {key!r}") from None

    instructions: list[_Instruction] = []
    offsets: list[int] = []
    while cursor < count:
        offsets.append(tokens[cursor][0])
        imp = take()
        if imp == _SPACE:
            command = take()
            if command == _SPACE:
                instructions.append(("push", number()))
            elif command == _LINE:
                instructions.append((choose(_STACK, take()), 0))
            else:
                kind = "copy" if take() == _SPACE else "slide"
                instructions.append((kind, number()))
        elif imp == _TAB:
            command = take()
            if command == _LINE:
                instructions.append((choose(_IO_KINDS, (take(), take())), 0))
            elif command == _TAB:
                instructions.append(
                    (choose({_SPACE: "store", _TAB: "retrieve"}, take()), 0)
                )
            else:
                instructions.append((choose(_ARITHMETIC, (take(), take())), 0))
        else:
            command = take()
            if command == _LINE:
                if take() != _LINE:
                    raise ProgramError("Whitespace has no flow command [LF][LF][..]")
                instructions.append(("end", 0))
            elif command == _TAB:
                sub = take()
                if sub == _LINE:
                    instructions.append(("return", 0))
                else:
                    instructions.append((choose(_BRANCH, sub), label()))
            else:
                instructions.append((choose(_LABELLED, (command, take())), label()))
    return instructions, offsets


def _parse_number(line: str) -> int:
    """Parse one complete signed ASCII decimal line."""
    # VM.hs ReadNum calls getLine: input_num would accept "2 3" and leave
    # its separator for a following character read.
    line = line.strip()
    if not re.fullmatch(r"[+-]?[0-9]+", line):
        raise syntax_error(
            f"input must be an integer line, got {line!r}",
            "supply one signed decimal integer per line, for example 42",
            error_type=ArgumentError,
        )
    return parse_integer(line)


_Image = tuple[tuple[_Instruction, ...], tuple[int, ...]]


def _prepare_source(code: str) -> _Image:
    instructions, offsets = _parse(code)
    if not instructions:
        raise ProgramError("Whitespace program is empty")
    labels: dict[str, int] = {}
    for index, (kind, argument) in enumerate(instructions):
        if kind == "mark":
            labels.setdefault(str(argument), index)
    for index, (kind, argument) in enumerate(instructions):
        if kind in {"call", "jump", "jz", "jn"} and isinstance(argument, str):
            # An unresolved spelling faults only if this transfer is taken.
            instructions[index] = kind, labels.get(argument, argument)
    return tuple(instructions), tuple(offsets)


type _StackEdit = tuple[int, tuple[int, ...]]


def _require(stack: Sequence[int], count: int) -> None:
    if len(stack) < count:
        raise HaltError(_EMPTY_STACK)


def _stack_edit(
    kind: str, arg: int, stack: Sequence[int], heap: Mapping[int, int]
) -> _StackEdit:
    """Return the suffix length to remove and the values to append."""
    if kind == "push":
        return 0, (arg,)
    if kind == "copy":
        if not 0 <= arg < len(stack):
            raise HaltError(f"'copy' asked for item {arg} of a {len(stack)}-item stack")
        return 0, (stack[-1 - arg],)
    if kind == "slide":
        if not stack:
            raise HaltError("'slide' needs a top item, and the stack is empty")
        return min(len(stack), max(0, arg) + 1), (stack[-1],)
    if kind in _OPERATIONS:
        _require(stack, 2)
        if kind in {"div", "mod"} and not stack[-1]:
            raise HaltError(f"'{kind}' divides by zero")
        return 2, (_OPERATIONS[kind](stack[-2], stack[-1]),)
    if kind == "swap":
        _require(stack, 2)
        return 2, (stack[-1], stack[-2])
    if kind == "store":
        _require(stack, 2)
        return 2, ()
    _require(stack, 1)
    if kind == "dup":
        return 0, (stack[-1],)
    if kind == "retrieve":
        return 1, (heap.get(stack[-1], 0),)
    if kind == "out_char" and not 0 <= stack[-1] <= 0x10FFFF:
        raise HaltError("character output is outside 0..0x10FFFF")
    return 1, ()


def _advance(
    pc: int,
    instruction: _Instruction,
    stack: Sequence[int],
    heap: Mapping[int, int],
    calls: Sequence[int],
) -> tuple[int, int, tuple[int, ...]]:
    """Resolve control and the operand edit before any machine or I/O effects."""
    kind, argument = instruction
    if kind == "return":
        if not calls:
            raise HaltError("'return' ran with no call to return from")
        return calls[-1], 0, ()
    if kind in {"mark", "end"}:
        return pc + 1, 0, ()
    if kind in {"call", "jump", "jn", "jz"}:
        conditional = kind in {"jn", "jz"}
        if conditional:
            _require(stack, 1)
            if stack[-1] != 0 if kind == "jz" else stack[-1] >= 0:
                return pc + 1, 1, ()
        if isinstance(argument, str):
            raise HaltError(f"'{kind}' names the undefined label {argument!r}")
        return argument, int(conditional), ()
    drop, append = _stack_edit(kind, int(argument), stack, heap)
    return pc + 1, drop, append


class _Machine:
    """One execution with private operand, heap, and return storage."""

    def __init__(self, code: str | _Image, io: IO) -> None:
        self.instructions, self.offsets = (
            _prepare_source(code) if isinstance(code, str) else code
        )
        self.io = io
        self._writer = _BufferedOutput()
        self.pc = 0
        self.ended = False
        self._operands: list[int] = []
        self.heap: dict[int, int] = {}
        self.calls: list[int] = []

    def _freeze_state(self) -> _State:
        return (
            self.pc,
            tuple(self._operands),
            tuple(sorted(self.heap.items())),
            tuple(self.calls),
            self.ended,
        )

    @property
    def halted(self) -> bool:
        """Whether ``end`` has run, or the pointer has left the program."""
        return self.ended or self.pc >= len(self.instructions)

    #: The position is a character offset into the source, so the debugger
    #: can mark the token the pointer stands on.
    ip_shape = "offset"

    @property
    def ip(self) -> int | None:
        return None if self.halted else self.offsets[self.pc]

    @property
    def stack(self) -> list[object]:
        return list(self._operands)

    def snapshot(self) -> tuple[object, ...]:
        boundary = (*self._freeze_state(), self.io.progress())
        return self._writer.snapshot(boundary)

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Count logical fields; ended records END, not falling off the code."""
        pc, stack, heap, calls, ended = self._freeze_state()
        accepted = self._writer.accepted
        return _WORKSPACE_MODEL.capture(
            instruction=(
                pc
                if accepted is None
                else WorkspaceVariant("pending_output", (pc, accepted))
            ),
            stack=tuple(stack),
            heap=tuple(heap),
            return_stack=tuple(calls),
            ended=ended,
            input_cursor=self.io.progress(),
        )

    def step(self) -> None:
        if self.halted:
            return
        instruction = self.instructions[self.pc]
        kind = instruction[0]
        stack = self._operands
        target, drop, append = _advance(
            self.pc, instruction, stack, self.heap, self.calls
        )
        if kind == "store":
            self._store(stack[-2], stack[-1])
        elif kind == "read_char":
            self._store(stack[-1], self.io.input_char())
        elif kind == "read_num":
            self._store(stack[-1], _parse_number(self.io.input_str()))
        elif kind in {"out_char", "out_num"}:
            self._output(kind, stack[-1])
            return
        elif kind == "call":
            self.calls.append(self.pc + 1)
        elif kind == "return":
            self.calls.pop()
        elif kind == "end":
            self.ended = True
        if drop:
            del stack[-drop:]
        if append:
            stack.extend(append)
        self.pc = target

    def _store(self, address: int, value: int) -> None:
        if value:
            self.heap[address] = value
        else:
            self.heap.pop(address, None)

    def _output(self, kind: str, value: int) -> None:
        io = self.io
        if isinstance(io, ScriptedIO):
            if kind == "out_char":
                char = chr(value)
                self._writer.write(io, char, first=partial(io.print_char, char))
            else:
                self._writer.write(
                    io, format_integer(value), first=partial(io.print_num, value)
                )
        self._operands.pop()
        self.pc += 1
        if not isinstance(io, ScriptedIO):
            if kind == "out_char":
                io.print_char(chr(value))
            else:
                io.print_num(value)


def prepare_machine(source: RunnerProgram, options: Mapping[str, Any]) -> RuntimePlan:
    """Parse source once and build fresh state for each run."""
    source = require_text_source(source, options, "Whitespace")
    image = _prepare_source(source)
    return RuntimePlan(lambda io: _Machine(image, io), lambda io: _execute(image, io))


def _execute(code: str | _Image, io: IO) -> CompletionReport:
    """Execute a Whitespace program."""
    machine = _Machine(code, io)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Execute a Whitespace program."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run, loader=text_source)
