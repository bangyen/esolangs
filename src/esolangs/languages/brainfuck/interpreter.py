"""Interpreter for Brainfuck.

8-bit wrapping tape growing in both directions, matching-bracket loops.

Input/output:
    ``,`` reads one byte and ``.`` writes one.  ``,`` at EOF raises (the
    spec leaves EOF undefined), so ``,[.,]`` ends with an error.

Errors:
    ProgramError: Unbalanced brackets.
    InputExhaustedError: ``,`` at EOF.

Decisions:
    * ``<`` at the leftmost cell adds a fresh zero cell to its left: the
      wiki allows cells left of the start ("an interpreter may provide
      some"), and its primo and KSab Hello Worlds need four and five.
"""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

from esolangs.runtime._entry import script_main
from esolangs.runtime.brackets import match_brackets as matches
from esolangs.runtime.io import IO

#: ``(ind, ptr, tape)``: an immutable value, rebound per step.  ``tape[ptr]``
#: is always the true cell: ``+``/``-`` write through, so one logical state
#: has one spelling and the cycle detector's hash sees a repeat as a repeat.
#: A buffered cell (an ``acc``/``dirty`` pair, one rebuild per run of
#: ``+``/``-`` instead of one per command) earned 17.5% run-to-halt but
#: cost 9.4% on the traced workload, whose ``snapshot()`` every step
#: commits the cell anyway; the traced workload is the one this repo's
#: verification drivers impose, so the buffer was removed (interpreter
#: candidate I-1).
#: A plain tuple: ``NamedTuple.__new__`` is Python-level, 2.7x slower to
#: build, and this is built once per step.  Code and bracket map are
#: parameters, not fields, so the cycle detector stores no constants.
#: Order starts ``ind, ptr, tape`` because ``snapshot`` returns those three.
type _State = tuple[int, int, tuple[int, ...]]
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


def _written(tape: tuple[int, ...], ptr: int, value: int) -> tuple[int, ...]:
    """Return ``tape`` with cell ``ptr`` set to ``value``.

    One rebuild per write; a tape is the handful of cells touched (nine
    to eighteen), so the rebuild stays small.
    """
    return (*tape[:ptr], value, *tape[ptr + 1 :])


# :func:`_advance` is pure over an immutable ``_State`` and ``snapshot`` returns it
# directly; the shell does ``.`` and ``,``. ``factor.py`` drives a decoded program
# through it.
def _advance(state: _State, code: str, brackets: dict[int, int]) -> _State:
    """Return the state after executing the command at the code position.

    Pure; ``,``'s value arrives already written.  Fields are unpacked and one
    state built at the end: per-branch rebuilds made this ~5.6x slower than
    the mutable original, against ~2x.
    """
    ind, ptr, tape = state
    char = code[ind]
    if char == "+":
        tape = _written(tape, ptr, (tape[ptr] + 1) % 256)
    elif char == "-":
        tape = _written(tape, ptr, (tape[ptr] - 1) % 256)
    elif char == ">":
        # Past the right end grows by one.
        ptr += 1
        if ptr == len(tape):
            tape = (*tape, 0)
    elif char == "<":
        # Past the left end grows by one, and the pointer stays at index 0,
        # now the new cell.
        if ptr:
            ptr -= 1
        else:
            tape = (0, *tape)
    elif (char == "[" and tape[ptr] == 0) or (char == "]" and tape[ptr] != 0):
        # Lands on the partner; +1 steps past it.
        ind = brackets[ind]
    return (ind + 1, ptr, tape)


class _Machine:
    """A Brainfuck run: one immutable ``_State``, rebound per step."""

    def __init__(self, code: str, io: IO) -> None:
        self.code = code
        self.io = io
        self.brackets = matches(code)
        # ``halted`` is read twice per command; take the length once.
        self.size = len(code)
        self.state: _State = (0, 0, (0,))

    # Views for ``factor.py``.

    @property
    def tape(self) -> tuple[int, ...]:
        return self.state[2]

    @property
    def ptr(self) -> int:
        return self.state[1]

    @property
    def ind(self) -> int:
        return self.state[0]

    def input_position(self) -> int:
        """Report the input cursor for the growth detector."""
        return self.io.progress()

    @property
    def halted(self) -> bool:
        return self.state[0] >= self.size

    # VM view.

    @property
    def ip(self) -> int:
        """The current instruction position."""
        return self.ind

    @property
    def memory(self) -> list[int]:
        """The addressable cells."""
        return list(self.tape)

    def snapshot(self) -> tuple[object, ...]:
        """Return the complete internal state, hashable for cycle detection."""
        # Tape plus input cursor (a repeat that ignores consumed input is
        # not a cycle).
        ind, ptr = self.state[0], self.state[1]
        return (ind, ptr, self.state[2], self.io.progress())

    def step(self) -> None:
        """Execute one command, advancing the code position.

        The shell does ``.`` and ``,``; ``,``'s value is written through
        before :func:`_advance` steps past it.
        """
        state = self.state
        if state[0] >= self.size:
            return
        ind, ptr, tape = state
        char = self.code[ind]
        if char == ".":
            self.io.print_char(chr(tape[ptr]))
        elif char == ",":
            # ``input_char`` is a whole code point.  Unreduced, ``,.`` echoed
            # an emoji while ``,+.`` printed ``\x01``.  CVNC does the same.
            state = (ind, ptr, _written(tape, ptr, self.io.input_char() % 256))
        self.state = _advance(state, self.code, self.brackets)


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
    brackets = matches(code)
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


def run(code: str, io: IO) -> None:
    """Run compact operations, applying the pure core's tape and IO effects."""
    ops = _compile(code)
    tape = bytearray(1)
    state: _CompiledState = (0, 0)
    while state[0] < len(ops):
        moved, effects, output, wants_read = _advance_compiled(state, ops, tape)
        if wants_read:
            moved, effects, output, _ = _advance_compiled(
                state, ops, tape, io.input_char()
            )
        prefix, suffix, writes = effects
        if prefix:
            tape[0:0] = bytes(prefix)
        if suffix:
            tape.extend(bytes(suffix))
        for at, value in writes:
            tape[at] = value
        state = moved
        if output is not None:
            io.print_char(output)


if __name__ == "__main__":
    script_main(run)
