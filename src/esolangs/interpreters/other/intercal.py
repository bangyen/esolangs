r"""Interpreter for the C-INTERCAL core used by the Boolean generator.

Supports scalar calculation with mingle, select, and unary logic; numeric
``WRITE IN``/``READ OUT``; ``NEXT``, ``RESUME``, ``FORGET``; and ``GIVE UP``.
EOF while reading and invalid programs raise ``HaltError``. The compiler's
politeness bounds count logical statements; LF is whitespace between tokens.

A number is read as one line of spelled-out digit words; the spec leaves its
text delimiter unspecified.
"""

from __future__ import annotations

import re
from itertools import pairwise

from esolangs.exceptions import HaltError
from esolangs.interpreters._entry import script_main
from esolangs.interpreters.io import IO

type _Value = tuple[int, int]
type _State = tuple[int, tuple[tuple[int, int], ...], tuple[int, ...]]

_DIGITS = {
    "ZERO": "0",
    "OH": "0",
    "ONE": "1",
    "TWO": "2",
    "THREE": "3",
    "FOUR": "4",
    "FIVE": "5",
    "SIX": "6",
    "SEVEN": "7",
    "EIGHT": "8",
    "NINE": "9",
    "NINER": "9",
}


def _unary(value: int, width: int, operator: str) -> int:
    mask = (1 << width) - 1
    rotated = ((value << 1) | (value >> (width - 1))) & mask
    if operator == "&":
        return value & rotated
    if operator == "V":
        return value | rotated
    return value ^ rotated


def _expression(
    text: str, variables: dict[int, int], at: int = 0
) -> tuple[_Value, int]:
    """Parse one fully grouped INTERCAL expression."""
    while at < len(text) and text[at].isspace():
        at += 1
    if at >= len(text):
        raise HaltError("incomplete INTERCAL expression")
    if text[at] in "'\"":
        delimiter = text[at]
        at += 1
        while at < len(text) and text[at].isspace():
            at += 1
        # A program truncated right after its delimiter leaves nothing to
        # read here; the entry guard above cannot see it, because `at` was
        # in range when this call began.
        if at >= len(text):
            raise HaltError("incomplete INTERCAL expression")
        unary = text[at] if text[at] in "&V?" else ""
        at += bool(unary)
        (left, width), at = _expression(text, variables, at)
        while at < len(text) and text[at].isspace():
            at += 1
        if at < len(text) and text[at] in "$~":
            operator = text[at]
            (right, right_width), at = _expression(text, variables, at + 1)
            if operator == "$":
                if width != 16 or right_width != 16:
                    raise HaltError("INTERCAL mingle needs two onespot values")
                left = sum(
                    (((left >> bit) & 1) << (2 * bit + 1))
                    | (((right >> bit) & 1) << (2 * bit))
                    for bit in range(16)
                )
                width = 32
            else:
                selected = [
                    (left >> bit) & 1
                    for bit in range(max(width, right_width))
                    if (right >> bit) & 1
                ]
                left = sum(bit << i for i, bit in enumerate(selected))
                width = 16 if len(selected) <= 16 else 32
        while at < len(text) and text[at].isspace():
            at += 1
        if at >= len(text) or text[at] != delimiter:
            raise HaltError("unbalanced INTERCAL expression group")
        return ((_unary(left, width, unary) if unary else left), width), at + 1
    match = re.match(r"([.#])(\d+)", text[at:])
    if match is None:
        raise HaltError("invalid INTERCAL operand")
    sigil, number = match.groups()
    value = int(number)
    return ((variables.get(value, 0) if sigil == "." else value), 16), at + len(
        match[0]
    )


def _roman(value: int) -> str:
    """Return the ordinary range of butchered Roman output."""
    numerals = (
        (1000, "M"),
        (900, "CM"),
        (500, "D"),
        (400, "CD"),
        (100, "C"),
        (90, "XC"),
        (50, "L"),
        (40, "XL"),
        (10, "X"),
        (9, "IX"),
        (5, "V"),
        (4, "IV"),
        (1, "I"),
    )
    out = []
    for amount, glyph in numerals:
        count, value = divmod(value, amount)
        out.append(glyph * count)
    return "".join(out)


_START = re.compile(
    r"(?<![A-Z])(?:\(\d+\)\s*)?(?:PLEASE(?:\s+DO)?|DO(?:\s+NOT)?|DON'T)\b"
)
_BARE = re.compile(
    r"(?:\.\d+\s*<-|READ\s+OUT|WRITE\s+IN|GIVE\s+UP|RESUME\b|FORGET\b|\(\d+\)\s+NEXT)"
)


def _statements(code: str) -> list[str]:
    """Assemble statements at identifiers, retaining bare core fixtures."""
    starts = [match.start() for match in _START.finditer(code)]
    bounds = [0, *starts, len(code)]
    statements: list[str] = []
    for left, right in pairwise(bounds):
        fragments: list[str] = []
        for line in code[left:right].splitlines():
            line = line.strip()
            if not line:
                continue
            # Bare complete commands remain physical-line statements; a
            # command after only an identifier completes that identifier.
            if fragments and _BARE.match(line):
                prefix = " ".join(fragments)
                if _START.fullmatch(prefix) is None:
                    statements.append(prefix)
                    fragments = []
            fragments.append(line)
        if fragments:
            statements.append(" ".join(fragments))
    return statements


class _Machine:
    """Parsed INTERCAL statements, variables, and NEXT stack."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self.lines = _statements(code)
        polite = sum(
            bool(re.match(r"(?:\(\d+\)\s+)?PLEASE", line)) for line in self.lines
        )
        if (
            not self.lines
            or polite * 5 < len(self.lines)
            or polite * 3 > len(self.lines)
        ):
            raise HaltError("INTERCAL program is insufficiently or excessively polite")
        self.labels: dict[int, int] = {}
        for i, line in enumerate(self.lines):
            found = re.match(r"\((\d+)\)", line)
            if found:
                self.labels[int(found.group(1))] = i
        self.state: _State = (0, (), ())

    @property
    def halted(self) -> bool:
        return self.state[0] >= len(self.lines)

    @property
    def ip(self) -> int:
        return self.state[0]

    @property
    def memory(self) -> list[int]:
        return [value for _name, value in self.state[1]]

    @property
    def stack(self) -> list[object]:
        return list(self.state[2])

    def snapshot(self) -> tuple[object, ...]:
        return (*self.state, self.io.position())

    def step(self) -> None:
        if self.halted:
            return
        ind, packed, stack = self.state
        variables = dict(packed)
        line = re.sub(r"^\(\d+\)\s+", "", self.lines[ind])
        inactive = line.startswith(("DON'T ", "DO NOT "))
        line = re.sub(r"^(?:PLEASE(?: DO)?|DO|DON'T|DO NOT)\s+", "", line)
        ind += 1
        if inactive:
            self.state = (ind, tuple(sorted(variables.items())), stack)
            return
        if " <- " in line:
            target, source = line.split(" <- ", 1)
            (value, _width), end = _expression(source, variables)
            if end != len(source) or not target.startswith("."):
                raise HaltError("invalid INTERCAL calculation")
            variables[int(target[1:])] = value & 0xFFFF
        elif line.startswith("READ OUT "):
            (value, _width), end = _expression(line[9:], variables)
            if end != len(line[9:]):
                raise HaltError("invalid INTERCAL output expression")
            self.io.print_str(_roman(value) + "\n")
        elif line.startswith("WRITE IN ."):
            words = self.io.input_str().upper().split()
            if not words or any(word not in _DIGITS for word in words):
                raise HaltError("invalid INTERCAL numeric input")
            variables[int(line[10:])] = int("".join(_DIGITS[word] for word in words))
        elif line.endswith(" NEXT") and line.startswith("("):
            label = int(line[1 : line.index(")")])
            stack = (*stack, ind)
            ind = self.labels[label]
        elif line.startswith(("RESUME ", "FORGET ")):
            command, source = line.split(" ", 1)
            (count, _width), end = _expression(source, variables)
            if end != len(source) or count == 0:
                raise HaltError("invalid INTERCAL stack count")
            if command == "RESUME":
                if count > len(stack):
                    raise HaltError("INTERCAL NEXT stack underflow")
                ind = stack[-count]
            stack = stack[: max(0, len(stack) - count)]
        elif line == "GIVE UP":
            ind = len(self.lines)
        else:
            raise HaltError(f"unsupported INTERCAL statement: {line}")
        self.state = (ind, tuple(sorted(variables.items())), stack)


def run(code: str, io: IO) -> None:
    """Execute an INTERCAL program."""
    machine = _Machine(code, io)
    while not machine.halted:
        machine.step()


if __name__ == "__main__":
    script_main(run)
