"""Complete buffered-bit boundaries from the unchanged old independent engine."""

from dataclasses import dataclass
from typing import NamedTuple

from tests.interpreters.semantic_oracles import Observation, bracket_pairs


class Prefix(NamedTuple):
    """Expose independent locals without changing one transition or parser rule."""

    observation: Observation
    control: tuple[int, ...]
    ones: frozenset[int]
    bit_at: int
    outgoing: tuple[int, ...]


def _finish(observation, pc, ptr, bit_at, cells, outgoing, stdin):
    offset = bit_at % 8
    remaining = (8 - offset) if offset else 0
    byte_at = (bit_at - 1) // 8
    byte = ord(stdin[byte_at]) % 256 if 0 <= byte_at < len(stdin) else 0
    incoming = byte >> offset if remaining else 0
    pending = (
        0 if observation.halted else sum(bit * 2**i for i, bit in enumerate(outgoing))
    )
    used = 0 if observation.halted else len(outgoing)
    return Prefix(
        observation,
        (pc, ptr, incoming, remaining, pending, used),
        frozenset(at for at, value in cells.items() if value),
        bit_at,
        tuple(outgoing),
    )


def _rich_prefix(code: str, stdin: str, cap: int) -> Prefix:
    pairs = bracket_pairs(code)
    cells = {}
    pc = ptr = consumed = bit_at = 0
    outgoing = []
    output = []
    for _ in range(cap):
        if pc == len(code):
            break
        command = code[pc]
        bit = cells.get(ptr, 0)
        if command == "+":
            cells[ptr] = 1 - bit
        elif command == "<":
            ptr -= 1
        elif command == ">":
            ptr += 1
        elif command == ",":
            byte_at = bit_at // 8
            byte = ord(stdin[byte_at]) % 256 if byte_at < len(stdin) else 0
            cells[ptr] = byte >> bit_at % 8 & 1
            bit_at += 1
            consumed = min(len(stdin), (bit_at + 7) // 8)
        elif command == ";":
            outgoing.append(bit)
            if len(outgoing) == 8:
                output.append(chr(sum((b * 2**i for i, b in enumerate(outgoing)))))
                outgoing.clear()
        elif command == "[" and (not bit):
            pc = pairs[pc]
        elif command == "]":
            pc = pairs[pc]
            continue
        pc += 1
    halted = pc == len(code)
    if halted and outgoing:
        output.append(chr(sum((b * 2**i for i, b in enumerate(outgoing)))))
    occupied = [at for at, value in cells.items() if value] + [0, ptr]
    memory = tuple(cells.get(at, 0) for at in range(min(occupied), max(occupied) + 1))
    return _finish(
        Observation("".join(output), memory, pc, consumed, halted),
        pc,
        ptr,
        bit_at,
        cells,
        outgoing,
        stdin,
    )


@dataclass(frozen=True)
class Row:
    """One complete computation and physical-IO boundary, including final padding."""

    control: tuple[int, ...] | None
    ones: frozenset[int] | None
    halted: bool
    output: str
    cursor: int
    reads: int
    past_end: int
    character_reads: bool
    newline: bool
    steps: int
    bit_at: int
    outgoing: tuple[int, ...]

    @property
    def parts(self):
        """Return every declared component in schema order."""
        return self.control, self.ones, self.cursor

    @property
    def legacy(self):
        """Keep the shared observer tuple unchanged."""
        state = None if self.control is None else (self.control, self.ones)
        return state, self.halted, self.output, self.cursor, self.cursor


def predict(source, stdin, cap=200):
    """Replay whole prefixes of the identical engine and derive its byte buffers."""
    rows = []
    reads = past = 0
    character = newline = False
    for step in range(cap + 1):
        try:
            prefix = _rich_prefix(source, stdin, step)
        except ValueError:
            assert not rows
            return "syntax", (
                Row(
                    control=None,
                    ones=None,
                    halted=False,
                    output="",
                    cursor=0,
                    reads=0,
                    past_end=0,
                    character_reads=False,
                    newline=False,
                    steps=0,
                    bit_at=0,
                    outgoing=(),
                ),
            )
        result = prefix.observation
        if rows:
            before = rows[-1]
            if prefix.bit_at != before.bit_at and before.bit_at % 8 == 0:
                character = True
                if before.bit_at // 8 < len(stdin):
                    reads += 1
                    newline = False
                else:
                    past += 1
            emitted = result.output[len(before.output) :]
            if emitted:
                newline = not emitted.endswith("\n")
        row = Row(
            prefix.control,
            prefix.ones,
            result.halted,
            result.output,
            result.consumed,
            reads,
            past,
            character,
            newline,
            step,
            prefix.bit_at,
            prefix.outgoing,
        )
        rows.append(row)
        if row.halted:
            return None, (*rows, row, row, row)
    return None, tuple(rows)


def legacy_prediction(source, stdin, cap=200):
    """Retain complete observer shape and caller's exact old bound."""
    error, rows = predict(source, stdin, cap)
    return error, [row.legacy for row in rows]
