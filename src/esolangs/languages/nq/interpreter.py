"""Interpreter for NQ.

An empty trit queue and flag 0 start at the first instruction. Source wraps
at its end; only H halts. Non-instruction characters are comments.

Commands:
    +N / +(trits) enqueue one trit or a sequence; l does so on the first lap
    >N / >N(body) execute the next instruction or group only when flag is N
    - dequeue into the flag; r / R enqueue one / all input trits
    W print the front without removing it; H halt

Input/output:
    Input trits are 0, 1, 2; whitespace separates them. W maps 0 to space,
    1 to newline and 2 to #. r at EOF raises; R reads through EOF.

Errors:
    ProgramError: missing or invalid operands, unclosed guard groups, invalid
    guard_binding, or a recursive guard without a complete lexical target.
    ArgumentError: input contains a non-trit other than whitespace.
    InputExhaustedError: r has no remaining trit.
    HaltError: - or W encounters an empty queue.

Decisions:
    * Input framing and empty-queue operations are unspecified: whitespace
      separates trits, R consumes the remaining stream, and underflow fails.
    * Empty/comment-only source is a no-op under the repository convention.
    * The instruction table governs guards; the cyclic-tag prose switches
      >1 to >0 for the same production. Groups nest lexically.
    * The page and its 13 revisions do not settle nested ungrouped guards
      or guard targets at source end. ``guard_binding="opcode"`` skips one
      opcode (a grouped guard includes its body) and permits wrapping.
      ``"recursive"`` skips the complete guarded instruction; its target
      must finish within the same lexical group or top-level source.
      ``+0->1>0+2WH`` prints # under opcode binding and underflows under
      recursive binding. Neither reading is claimed as author intent.
      Generated programs use grouped guards and agree under both readings.
"""

from __future__ import annotations

from collections import deque
from typing import NamedTuple

from esolangs.exceptions import ArgumentError, HaltError
from esolangs.runtime._drive import drive
from esolangs.runtime._entry import script_main
from esolangs.runtime._lifecycle import CompletionReport
from esolangs.runtime.io import IO
from esolangs.runtime.source_hints import syntax_error

GUARD_BINDINGS = ("opcode", "recursive")


def guard_dialect(guard_binding: str = "opcode") -> None:
    """Validate the explicit reading of an ungrouped guard's target."""
    if guard_binding not in GUARD_BINDINGS:
        raise ValueError("guard_binding must be opcode or recursive")


class _Instruction(NamedTuple):
    opcode: str
    values: tuple[int, ...]
    target: int
    offset: int


class _State(NamedTuple):
    cursor: int
    flag: int
    first: bool
    stopped: bool


class _Effect(NamedTuple):
    append: tuple[int, ...] = ()
    pop: bool = False
    output: str = ""


def _operand(source: str, cursor: int) -> tuple[tuple[int, ...], int]:
    """Read a trit or an enqueue list, preserving the next source offset."""
    while cursor < len(source) and source[cursor].isspace():
        cursor += 1
    if cursor < len(source) and source[cursor] in "012":
        return (int(source[cursor]),), cursor + 1
    if cursor >= len(source) or source[cursor] != "(":
        raise syntax_error("missing trit operand", "use 0, 1, 2 or (trits)")
    end = source.find(")", cursor + 1)
    if end < 0:
        raise syntax_error("unclosed trit list", "close the list with )")
    text = source[cursor + 1 : end]
    if any(c not in "012" and not c.isspace() for c in text):
        raise syntax_error("invalid trit list", "use only 0, 1, 2 and whitespace")
    return tuple(int(c) for c in text if not c.isspace()), end + 1


def _parse(source: str, *, guard_binding: str = "opcode") -> tuple[_Instruction, ...]:
    """Compile lexical groups and single-instruction guards without recursion."""
    guard_dialect(guard_binding)
    commands: list[_Instruction] = []
    owners: dict[int, int] = {}
    groups: list[int] = []
    cursor = 0
    while cursor < len(source):
        offset = cursor
        c = source[cursor]
        cursor += 1
        if c == ")":
            if groups:
                start = groups.pop()
                commands[start] = commands[start]._replace(target=len(commands))
        elif c in "+l":
            values, cursor = _operand(source, cursor)
            # Skip the Python constructor wrapper.
            # [interpreter_ablations.speedup_adoption_20261103]
            commands.append(tuple.__new__(_Instruction, (c, values, -1, offset)))
        elif c == ">":
            while cursor < len(source) and source[cursor].isspace():
                cursor += 1
            if cursor >= len(source) or source[cursor] not in "012":
                raise syntax_error("guard needs a trit", "use >0, >1 or >2")
            value = int(source[cursor])
            cursor += 1
            while cursor < len(source) and source[cursor].isspace():
                cursor += 1
            grouped = cursor < len(source) and source[cursor] == "("
            commands.append(
                tuple.__new__(
                    _Instruction, (c, (value,), -1 if grouped else -2, offset)
                )
            )
            if grouped:
                groups.append(len(commands) - 1)
                cursor += 1
            else:
                owners[len(commands) - 1] = groups[-1] if groups else -1
        elif c in "-rRWH":
            commands.append(tuple.__new__(_Instruction, (c, (), -1, offset)))
    if groups:
        raise syntax_error("unclosed guard group", "close each >N( with )")
    return _targets(commands, owners, guard_binding=guard_binding)


def _targets(
    commands: list[_Instruction], owners: dict[int, int], *, guard_binding: str
) -> tuple[_Instruction, ...]:
    """Resolve target extents, preserving grouped instructions across wrap."""
    # >0(+2)W>1 must wrap past the whole first group, not enter its +2.
    first_end = commands[0].target if commands and commands[0].target >= 0 else 1
    ends = [i + 1 for i in range(len(commands))]
    for i in range(len(commands) - 1, -1, -1):
        command = commands[i]
        if command.target == -2:
            if guard_binding == "recursive":
                owner = owners[i]
                boundary = commands[owner].target if owner >= 0 else len(commands)
                if i + 1 >= boundary:
                    raise syntax_error(
                        "recursive guard needs a complete instruction",
                        "put its target before the lexical group or source ends",
                    )
                ends[i] = ends[i + 1]
            commands[i] = command._replace(
                target=ends[i + 1]
                if i + 1 < len(commands)
                else len(commands) + first_end
            )
        elif command.opcode == ">":
            ends[i] = command.target
    return tuple(commands)


def _advance(
    state: _State,
    command: _Instruction,
    length: int,
    front: int | None,
    inputs: tuple[int, ...] = (),
) -> tuple[_State, _Effect]:
    """Return the immutable transition and queue/output effects."""
    cursor, flag, first, stopped = state
    cursor += 1
    effect = _Effect()
    c = command.opcode
    if c == "+" or (c == "l" and first):
        effect = _Effect(append=command.values)
    elif c in "rR":
        effect = _Effect(append=inputs)
    elif c == ">" and flag != command.values[0]:
        cursor = command.target
    elif c in "-W":
        if front is None:
            raise HaltError("NQ queue underflow")
        if c == "-":
            flag, effect = front, _Effect(pop=True)
        else:
            effect = _Effect(output=(" ", "\n", "#")[front])
    elif c == "H":
        stopped = True
    if cursor >= length:
        cursor, first = cursor % length, False
    return tuple.__new__(_State, (cursor, flag, first, stopped)), effect


def _trits(text: str) -> tuple[int, ...]:
    """Validate input, permitting whitespace as framing rather than data."""
    if any(c not in "012" and not c.isspace() for c in text):
        raise syntax_error(
            "input must contain trits", "use 0, 1 or 2", error_type=ArgumentError
        )
    return tuple(int(c) for c in text if not c.isspace())


class _Machine:
    """A queue with immutable control state and precompiled guard targets."""

    def __init__(self, code: str, io: IO, *, guard_binding: str = "opcode") -> None:
        self.code = _parse(code, guard_binding=guard_binding)
        self.state = _State(0, 0, first=True, stopped=not self.code)
        self.queue: deque[int] = deque()
        self.io = io

    @property
    def halted(self) -> bool:
        """Whether H executed, or the source contained no instructions."""
        return self.state.stopped

    @property
    def ip(self) -> int | None:
        """Original source offset of the next instruction."""
        return None if self.halted else self.code[self.state.cursor].offset

    @property
    def memory(self) -> list[int]:
        """Queued trits, front first."""
        return list(self.queue)

    def snapshot(self) -> tuple[object, ...]:
        """Include the flag, first-lap status, queue and input progress."""
        return (*self.state, tuple(self.queue), self.io.progress())

    def step(self) -> None:
        """Read input, apply one pure transition, then perform its effects."""
        if self.halted:
            return
        command = self.code[self.state.cursor]
        inputs: tuple[int, ...] = ()
        if command.opcode == "r":
            text = chr(self.io.input_char())
            while text.isspace():
                text = chr(self.io.input_char())
            inputs = _trits(text)
        elif command.opcode == "R":
            inputs = _trits(self.io.input_all())
        self.state, effect = _advance(
            self.state,
            command,
            len(self.code),
            self.queue[0] if self.queue else None,
            inputs,
        )
        if effect.pop:
            self.queue.popleft()
        self.queue.extend(effect.append)
        if effect.output:
            self.io.print_str(effect.output)


def _execute(code: str, io: IO, *, guard_binding: str = "opcode") -> CompletionReport:
    """Run NQ until H; a nonempty source without H can wrap forever."""
    return drive(_Machine(code, io, guard_binding=guard_binding))


def run(code: str, io: IO, *, guard_binding: str = "opcode") -> None:
    """Run NQ until H; a nonempty source without H can wrap forever."""
    _execute(code, io, guard_binding=guard_binding)


if __name__ == "__main__":
    script_main(run)
