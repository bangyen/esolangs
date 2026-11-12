"""Complete bounded state from the unchanged old independent byte-tape rules."""

from dataclasses import dataclass
from typing import NamedTuple

from tests.interpreters.semantic_oracles import bracket_pairs


class Prefix(NamedTuple):
    """Expose original locals before a failed input and at a normal boundary."""

    error: str | None
    pc: int
    ptr: int
    tape: tuple[int, ...]
    consumed: int
    output: str
    halted: bool
    before_failure: int | None


def _rich_prefix(code: str, stdin: str, cap: int):
    """Interpret raw commands with a separately parsed bracket stack."""
    pairs = bracket_pairs(code)
    tape = [0]
    pc = ptr = consumed = 0
    output = []
    for _ in range(cap):
        if pc == len(code):
            break
        command = code[pc]
        if command in "+-":
            tape[ptr] = (tape[ptr] + (1 if command == "+" else -1)) % 256
        elif command == ">":
            ptr += 1
            if ptr == len(tape):
                tape.append(0)
        elif command == "<":
            if ptr:
                ptr -= 1
            else:
                tape.insert(0, 0)
        elif command == ",":
            if consumed == len(stdin):
                return Prefix(
                    "input",
                    pc,
                    ptr,
                    tuple(tape),
                    consumed,
                    "".join(output),
                    halted=False,
                    before_failure=_,
                )
            tape[ptr] = ord(stdin[consumed]) % 256
            consumed += 1
        elif command == ".":
            output.append(chr(tape[ptr]))
        elif (command == "[" and (not tape[ptr])) or (command == "]" and tape[ptr]):
            pc = pairs[pc]
        pc += 1
    return Prefix(
        None, pc, ptr, tuple(tape), consumed, "".join(output), pc == len(code), None
    )


@dataclass(frozen=True)
class Row:
    """Every semantic and owned-IO field, including an attempted EOF read."""

    pc: int | None
    ptr: int | None
    tape: tuple[int, ...] | None
    output: str
    cursor: int
    reads: int
    past_end: int
    character_reads: bool
    newline: bool
    halted: bool
    steps: int

    @property
    def parts(self):
        """Return the complete declared workspace in component order."""
        return self.pc, self.ptr, self.tape, self.cursor

    @property
    def legacy(self):
        """Retain the generic observer's original full-state tuple."""
        state = None if self.pc is None else (self.pc, self.ptr, self.tape)
        return state, self.halted, self.output, self.cursor, self.cursor


def predict(source, stdin, cap=200):
    """Replay the same old prefixes and retain the exact failed-read boundary."""
    rows = []
    character = newline = False
    for step in range(cap + 1):
        try:
            value = _rich_prefix(source, stdin, step)
        except ValueError:
            assert not rows
            return "syntax", (
                Row(
                    None,
                    None,
                    None,
                    "",
                    0,
                    0,
                    0,
                    character_reads=False,
                    newline=False,
                    halted=False,
                    steps=0,
                ),
            )
        if rows:
            previous = rows[-1]
            if value.consumed != previous.cursor or value.error == "input":
                character = True
                if value.error is None:
                    newline = False
            suffix = value.output[len(previous.output) :]
            if suffix:
                newline = not suffix.endswith("\n")
        row = Row(
            value.pc,
            value.ptr,
            value.tape,
            value.output,
            value.consumed,
            value.consumed,
            int(value.error == "input"),
            character,
            newline,
            value.halted,
            value.before_failure if value.error else step,
        )
        rows.append(row)
        if value.error:
            return value.error, tuple(rows)
        if value.halted:
            return None, (*rows, row, row, row)
    return None, tuple(rows)


def legacy_prediction(source, stdin, cap=200):
    """Keep all fields and the old observer's explicit error classification."""
    error, rows = predict(source, stdin, cap)
    return error, [row.legacy for row in rows]
