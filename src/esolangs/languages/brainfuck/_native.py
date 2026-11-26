"""Lower Brainfuck source and compute the compiled tape effects."""

from collections.abc import Mapping, Sequence
from functools import lru_cache

from esolangs.runtime.brackets import match_brackets as matches

type _Op = tuple[int, int]

_ADD = 0
_RIGHT = 1
_LEFT = 2
_OUTPUT = 3
_INPUT = 4
_OPEN = 5
_CLOSE = 6
_CLEAR = 7
_TRANSFER_RIGHT = 8
_JUMP_OR_IO = {".": _OUTPUT, ",": _INPUT, "[": _OPEN, "]": _CLOSE}


def _net_change(code: str, start: int) -> tuple[int, int]:
    """Return the net ``+``/``-`` count of the run at ``start``, and its end."""
    end = start
    while end < len(code) and code[end] in "+-":
        end += 1
    run = code[start:end]
    return run.count("+") - run.count("-"), end


@lru_cache(maxsize=16)
def _compile(code: str) -> tuple[_Op, ...]:
    """Return compact operations for the effect-driven run path."""
    return _compile_ops(code, matches(code))


def _compile_ops(code: str, brackets: Mapping[int, int]) -> tuple[_Op, ...]:
    """Lower validated source for the native runner, preserving its loop targets."""
    ops: list[_Op] = []
    op_at: dict[int, int] = {}
    ind = 0
    while ind < len(code):
        char = code[ind]
        if char in "+-":
            change, ind = _net_change(code, ind)
            if change % 256:
                ops.append((_ADD, change % 256))
            continue
        if char in "><":
            end = ind + 1
            while end < len(code) and code[end] == char:
                end += 1
            ops.append((_RIGHT if char == ">" else _LEFT, end - ind))
            ind = end
            continue
        if code.startswith(("[-]", "[+]"), ind):
            ops.append((_CLEAR, 0))
            ind += len("[-]")
            continue
        if code.startswith("[>", ind):
            change, end = _net_change(code, ind + len("[>"))
            if end > ind + len("[>") and code.startswith("<-]", end):
                ops.append((_TRANSFER_RIGHT, change % 256))
                ind = end + len("<-]")
                continue
        if char in _JUMP_OR_IO:
            op_at[ind] = len(ops)
            ops.append((_JUMP_OR_IO[char], brackets.get(ind, 0)))
        ind += 1
    for at, (opcode, target) in enumerate(ops):
        if opcode in (_OPEN, _CLOSE):
            ops[at] = (opcode, op_at[target])
    return tuple(ops)


#: The compiled cursor and pointer; the shell owns the byte buffer.
type _CompiledState = tuple[int, int]
type _TapeEffects = tuple[int, int, tuple[tuple[int, int], ...]]


def _advance_compiled(
    state: _CompiledState,
    ops: tuple[_Op, ...],
    tape: Sequence[int],
    byte: int | None = None,
) -> tuple[_CompiledState, _TapeEffects, str | None, bool]:
    """Return cursor, tape edits, output, and whether a byte is needed.

    The borrowed tape is read-only here; edits leave as values so the shell
    keeps O(1) cell writes without copying the buffer per command.
    """
    ind, ptr = state
    prefix = suffix = 0
    writes: tuple[tuple[int, int], ...] = ()
    output = None
    if ind >= len(ops):
        return state, (prefix, suffix, writes), output, False
    opcode, arg = ops[ind]
    if opcode == _ADD:
        writes = ((ptr, (tape[ptr] + arg) % 256),)
    elif opcode == _RIGHT:
        ptr += arg
        suffix = max(0, ptr + 1 - len(tape))
    elif opcode == _LEFT:
        ptr -= arg
        if ptr < 0:
            # Doubling preserves linear growth when the program marches left.
            prefix = max(-ptr, len(tape))
            ptr += prefix
    elif opcode == _OUTPUT:
        output = chr(tape[ptr])
    elif opcode == _INPUT:
        if byte is None:
            return state, (prefix, suffix, writes), output, True
        writes = ((ptr, byte % 256),)
    elif (opcode == _OPEN and tape[ptr] == 0) or (opcode == _CLOSE and tape[ptr] != 0):
        ind = arg
    elif opcode == _CLEAR:
        writes = ((ptr, 0),)
    elif opcode == _TRANSFER_RIGHT:
        suffix = int(ptr + 1 == len(tape))
        neighbor = 0 if suffix else tape[ptr + 1]
        writes = ((ptr + 1, (neighbor + tape[ptr] * arg) % 256), (ptr, 0))
    return (ind + 1, ptr), (prefix, suffix, writes), output, False
