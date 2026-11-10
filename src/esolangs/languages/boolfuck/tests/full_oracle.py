"""Complete buffered-bit boundaries from the unchanged old independent engine."""

from dataclasses import dataclass, replace
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
    def memory(self):
        """Trim only zeros beyond pointer and origin."""
        if self.control is None:
            return None
        occupied = self.ones | {0, self.control[1]}
        return tuple(
            int(at in self.ones) for at in range(min(occupied), max(occupied) + 1)
        )

    @property
    def pc(self):
        """Expose the independently stepped source offset."""
        return None if self.control is None else self.control[0]

    @property
    def legacy(self):
        """Keep the shared observer tuple unchanged."""
        state = None if self.control is None else (self.control, self.ones)
        return state, self.halted, self.output, self.cursor, self.cursor

    def io_fields(self, stdin):
        """Predict all11 ScriptedIO fields; exhausted byte reads preserve newline."""
        return {
            "_source": stdin,
            "_supplied": stdin.count("\n")
            + int(bool(stdin) and not stdin.endswith("\n")),
            "_offset": self.cursor,
            "_line_reads": 0,
            "_character_reads": self.character_reads,
            "_past_end": self.past_end,
            "_pending": "",
            "_reads": self.reads,
            "_consumed": self.cursor,
            "_newline": self.newline,
            "_buffer": (self.output, "\n", len(self.output), None),
        }


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


def refusal_history(source, stdin, *, provider, partial=False):
    """Model the two write commit phases without inventing a retry after halt."""
    error, rows = predict(source, stdin)
    assert error is None
    at = next(
        index
        for index in range(1, len(rows))
        if (
            rows[index].bit_at != rows[index - 1].bit_at
            if provider
            else rows[index].output != rows[index - 1].output
        )
    )
    before, after = rows[at - 1], rows[at]
    prefix = "" if provider or not partial else after.output[len(before.output) :]
    assert len(prefix) <= 1
    if not provider and after.halted and after.outgoing:
        pending = sum(bit * 2**i for i, bit in enumerate(after.outgoing))
        control = (*after.control[:4], pending, len(after.outgoing))
        failed = replace(
            after,
            control=control,
            output=before.output + prefix,
            newline=before.newline,
            steps=before.steps,
        )
        return at, (*rows[:at], failed, failed, failed, failed)
    failed = replace(before, output=before.output + prefix)
    suffix = [
        replace(row, output=before.output + prefix + row.output[len(before.output) :])
        for row in rows[at:]
    ]
    return at, (*rows[:at], failed, *suffix)
