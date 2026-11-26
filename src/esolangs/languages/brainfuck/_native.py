"""Compile Brainfuck and execute native operations on a mutable byte tape."""

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache

from esolangs.runtime.brackets import match_brackets as matches
from esolangs.runtime.io import IO


@dataclass(frozen=True, slots=True)
class _Transfer:
    """Visited offsets and per-iteration changes relative to the source cell."""

    left: int
    right: int
    factors: tuple[tuple[int, int], ...]


type _Op = tuple[int, int] | _Transfer

_ADD = 0
_RIGHT = 1
_LEFT = 2
_OUTPUT = 3
_INPUT = 4
_OPEN = 5
_CLOSE = 6
_CLEAR = 7
_JUMP_OR_IO = {".": _OUTPUT, ",": _INPUT, "[": _OPEN, "]": _CLOSE}


def _net_change(code: str, start: int) -> tuple[int, int]:
    """Return the net ``+``/``-`` count of the run at ``start``, and its end."""
    end = start
    while end < len(code) and code[end] in "+-":
        end += 1
    run = code[start:end]
    return run.count("+") - run.count("-"), end


def _transfer(code: str, start: int, stop: int) -> _Transfer | None:
    """Summarize a flat loop with unit decrement and zero pointer displacement."""
    offset = left = right = 0
    changes: dict[int, int] = {}
    for index in range(start + 1, stop):
        char = code[index]
        if char == ">":
            offset += 1
            right = max(right, offset)
        elif char == "<":
            offset -= 1
            left = min(left, offset)
        elif char in "+-":
            changes[offset] = changes.get(offset, 0) + (1 if char == "+" else -1)
        elif char in "[].,":
            return None
    if offset or changes.pop(0, 0) != -1:
        return None
    return _Transfer(
        left,
        right,
        tuple(
            (offset, change % 256) for offset, change in changes.items() if change % 256
        ),
    )


@lru_cache(maxsize=16)
def _compile(code: str) -> tuple[_Op, ...]:
    """Return compact operations for the run-to-halt path."""
    return _compile_ops(code, matches(code))


def _compile_ops(
    code: str,
    brackets: Mapping[int, int],
    *,
    spans: list[tuple[int, int]] | None = None,
) -> tuple[_Op, ...]:
    """Lower source, optionally retaining half-open spans for verification."""
    ops: list[_Op] = []
    op_at: dict[int, int] = {}
    ind = 0
    while ind < len(code):
        start = ind
        char = code[ind]
        op: _Op
        if char in "+-":
            change, ind = _net_change(code, ind)
            if not change % 256:
                continue
            op = (_ADD, change % 256)
        elif char in "><":
            ind += 1
            while ind < len(code) and code[ind] == char:
                ind += 1
            op = (_RIGHT if char == ">" else _LEFT, ind - start)
        elif code.startswith(("[-]", "[+]"), ind):
            op = (_CLEAR, 0)
            ind += len("[-]")
        elif (
            char == "["
            and (transfer := _transfer(code, ind, brackets[ind])) is not None
        ):
            op = transfer
            ind = brackets[ind] + 1
        elif char in _JUMP_OR_IO:
            op_at[ind] = len(ops)
            op = (_JUMP_OR_IO[char], brackets.get(ind, 0))
            ind += 1
        else:
            ind += 1
            continue
        ops.append(op)
        if spans is not None:
            spans.append((start, ind))
    for at, entry in enumerate(ops):
        if isinstance(entry, tuple) and entry[0] in (_OPEN, _CLOSE):
            ops[at] = (entry[0], op_at[entry[1]])
    return tuple(ops)


#: The compiled cursor and pointer; the shell owns the byte buffer.
type _CompiledState = tuple[int, int]


def _advance_compiled(
    state: _CompiledState, ops: tuple[_Op, ...], tape: bytearray, io: IO
) -> _CompiledState:
    """Execute one native instruction on this run's tape and IO."""
    ind, ptr = state
    op = ops[ind]
    if isinstance(op, _Transfer):
        value = tape[ptr]
        if value:
            if ptr + op.left < 0:
                prefix = max(-(ptr + op.left), len(tape))
                tape[:0] = bytes(prefix)
                ptr += prefix
            if ptr + op.right >= len(tape):
                tape.extend(bytes(ptr + op.right + 1 - len(tape)))
            for offset, factor in op.factors:
                tape[ptr + offset] = (tape[ptr + offset] + value * factor) % 256
            tape[ptr] = 0
        return ind + 1, ptr
    opcode, arg = op
    if opcode == _ADD:
        tape[ptr] = (tape[ptr] + arg) % 256
    elif opcode == _RIGHT:
        ptr += arg
        if ptr >= len(tape):
            tape.extend(bytes(ptr + 1 - len(tape)))
    elif opcode == _LEFT:
        ptr -= arg
        if ptr < 0:
            prefix = max(-ptr, len(tape))
            tape[:0] = bytes(prefix)
            ptr += prefix
    elif opcode == _OUTPUT:
        io.print_char(chr(tape[ptr]))
    elif opcode == _INPUT:
        tape[ptr] = io.input_char() % 256
    elif (opcode == _OPEN and tape[ptr] == 0) or (opcode == _CLOSE and tape[ptr] != 0):
        ind = arg
    elif opcode == _CLEAR:
        tape[ptr] = 0
    return ind + 1, ptr
