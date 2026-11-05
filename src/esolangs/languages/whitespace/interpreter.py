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
    * Conditional branches resolve labels only when taken, as VM.hs does.
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
from collections.abc import Callable, Mapping
from functools import partial
from operator import floordiv, mod
from typing import Any

from esolangs.exceptions import ArgumentError, HaltError, ProgramError
from esolangs.languages.whitespace.lifecycle import CAPABILITIES
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime._machine import MachineFactory
from esolangs.runtime._program import RunnerProgram
from esolangs.runtime._source import ProgramSource, _read_container, text_source
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import IO
from esolangs.runtime.memory import parse_integer
from esolangs.runtime.source_hints import syntax_error

_SPACE, _TAB, _LINE = " ", "\t", "\n"
type _Instruction = tuple[str, int | str]
type _Heap = tuple[tuple[int, int], ...]
type _State = tuple[int, tuple[int, ...], _Heap, tuple[int, ...], bool]
type _Effect = tuple[str, int] | None

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


def _read_heap(heap: _Heap, address: int) -> int:
    for index, value in heap:
        if index == address:
            return value
    return 0


def _write_heap(heap: _Heap, address: int, value: int) -> _Heap:
    updated = dict(heap)
    if value:
        updated[address] = value
    else:
        updated.pop(address, None)
    return tuple(sorted(updated.items()))


def _pop(stack: tuple[int, ...]) -> tuple[int, tuple[int, ...]]:
    if not stack:
        raise HaltError("the stack is empty, so there is no top to pop")
    return stack[-1], stack[:-1]


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


def _rearrange(kind: str, depth: int, stack: tuple[int, ...]) -> tuple[int, ...]:
    """Return the stack after a dup, swap, discard, copy or slide."""
    if kind == "dup":
        return (*stack, _pop(stack)[0])
    if kind == "swap":
        first, stack = _pop(stack)
        second, stack = _pop(stack)
        return (*stack, first, second)
    if kind == "discard":
        return _pop(stack)[1]
    if kind == "copy":
        if not 0 <= depth < len(stack):
            raise HaltError(
                f"'copy' asked for item {depth} of a {len(stack)}-item stack"
            )
        return (*stack, stack[-1 - depth])
    if not stack:
        raise HaltError("'slide' needs a top item, and the stack is empty")
    below = stack[:-1]
    return (*below[: max(0, len(below) - depth)], stack[-1])


def _flow(
    kind: str,
    label: str,
    labels: dict[str, int],
    frame: tuple[int, tuple[int, ...], tuple[int, ...]],
) -> tuple[tuple[int, ...], tuple[int, ...], int]:
    """Return the stack, call stack and next pc after a labelled jump."""
    pc, stack, calls = frame
    if kind in {"jz", "jn"}:
        value, stack = _pop(stack)
        if not ((value == 0) if kind == "jz" else (value < 0)):
            return stack, calls, pc + 1
    target = labels.get(label)
    if target is None:
        raise HaltError(f"'{kind}' names the undefined label {label!r}")
    if kind == "call":
        return stack, (*calls, pc + 1), target
    return stack, calls, target


def _advance(
    state: _State,
    instructions: list[_Instruction],
    labels: dict[str, int],
    char_input: int | None = None,
    number_input: int | None = None,
) -> tuple[_State, _Effect]:
    """Return the next state and an output effect, if this command emits."""
    pc, stack, heap, calls, done = state
    if done:
        return state, None
    kind, argument = instructions[pc]
    effect, jump = None, pc + 1

    if kind == "push":
        stack = (*stack, int(argument))
    elif kind in {"dup", "swap", "discard", "copy", "slide"}:
        stack = _rearrange(kind, int(argument), stack)
    elif kind in _OPERATIONS:
        right, stack = _pop(stack)
        left, stack = _pop(stack)
        if kind in {"div", "mod"} and not right:
            raise HaltError(f"'{kind}' divides by zero")
        result = _OPERATIONS[kind](left, right)
        stack = (*stack, result)
    elif kind == "store":
        value, stack = _pop(stack)
        address, stack = _pop(stack)
        heap = _write_heap(heap, address, value)
    elif kind == "retrieve":
        address, stack = _pop(stack)
        stack = (*stack, _read_heap(heap, address))
    elif kind in {"out_char", "out_num"}:
        value, stack = _pop(stack)
        if kind == "out_char" and not 0 <= value <= 0x10FFFF:
            raise HaltError("character output is outside 0..0x10FFFF")
        effect = ("char" if kind == "out_char" else "num", value)
    elif kind == "read_char":
        address, stack = _pop(stack)
        if char_input is None:
            raise HaltError("'read_char' reads and there is no input left")
        heap = _write_heap(heap, address, char_input)
    elif kind == "read_num":
        address, stack = _pop(stack)
        if number_input is None:
            raise HaltError("'read_num' reads and there is no input left")
        heap = _write_heap(heap, address, number_input)
    elif kind == "mark":
        pass
    elif kind in {"call", "jump", "jz", "jn"}:
        stack, calls, jump = _flow(kind, str(argument), labels, (pc, stack, calls))
    elif kind == "return":
        if not calls:
            raise HaltError("'return' ran with no call to return from")
        jump, calls = calls[-1], calls[:-1]
    else:
        done = True
    return (jump, stack, heap, calls, done), effect


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


class _Machine:
    """Protocol shell holding one immutable Whitespace state value."""

    def __init__(self, code: str, io: IO) -> None:
        self.instructions, self.offsets = _parse(code)
        if not self.instructions:
            raise ProgramError("Whitespace program is empty")
        self.io = io
        self.labels: dict[str, int] = {}
        for index, (kind, argument) in enumerate(self.instructions):
            if kind == "mark":
                self.labels.setdefault(str(argument), index)
        self.state: _State = (0, (), (), (), False)

    @property
    def halted(self) -> bool:
        """Whether ``end`` has run, or the pointer has left the program."""
        return self.state[4] or self.state[0] >= len(self.instructions)

    #: The position is a character offset into the source, so the debugger
    #: can mark the token the pointer stands on.
    ip_shape = "offset"

    @property
    def ip(self) -> int | None:
        return None if self.halted else self.offsets[self.state[0]]

    @property
    def stack(self) -> list[object]:
        return list(self.state[1])

    def snapshot(self) -> tuple[object, ...]:
        return (*self.state, self.io.progress())

    def workspace_snapshot(self) -> WorkspaceSnapshot:
        """Count logical fields; ended records END, not falling off the code."""
        pc, stack, heap, calls, ended = self.state
        return _WORKSPACE_MODEL.capture(
            instruction=pc,
            stack=tuple(stack),
            heap=tuple(heap),
            return_stack=tuple(calls),
            ended=ended,
            input_cursor=self.io.progress(),
        )

    def step(self) -> None:
        if self.halted:
            return
        kind = self.instructions[self.state[0]][0]
        char_input = self.io.input_char() if kind == "read_char" else None
        number_input = (
            _parse_number(self.io.input_str()) if kind == "read_num" else None
        )
        self.state, effect = _advance(
            self.state, self.instructions, self.labels, char_input, number_input
        )
        if effect:
            out_kind, value = effect
            if out_kind == "char":
                self.io.print_char(chr(value))
            else:
                self.io.print_num(value)


def load_source(source: ProgramSource) -> str:
    """Preserve command line feeds, including the last byte of a file."""
    value, _path = _read_container(source)
    return text_source(value)


def prepare_machine(
    source: RunnerProgram, options: Mapping[str, Any]
) -> MachineFactory:
    """Bind fresh source-step machines; Whitespace has no runtime options."""
    if not isinstance(source, str):
        raise TypeError("Whitespace machines require text source")
    if options:
        raise TypeError("Whitespace machines accept no runtime options")
    return partial(_Machine, source)


def _execute(code: str, io: IO) -> CompletionReport:
    """Execute a Whitespace program."""
    machine = _Machine(code, io)
    return drive(machine, policy=CAPABILITIES.completion)


def run(code: str, io: IO) -> None:
    """Execute a Whitespace program."""
    _execute(code, io)


if __name__ == "__main__":
    script_main(run, loader=load_source)
