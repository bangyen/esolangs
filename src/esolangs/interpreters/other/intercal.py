r"""Interpreter for the C-INTERCAL core used by the Boolean generator.

Supports scalar calculation with mingle, select, and unary logic; numeric
``WRITE IN``/``READ OUT``; ``NEXT``, ``RESUME``, ``FORGET``; and ``GIVE UP``.
EOF raises ``EOFError``; invalid programs raise ``HaltError``. The compiler's
politeness bounds count logical statements; LF is whitespace between tokens.

A number is read as one line of spelled-out digit words; the spec leaves its
text delimiter unspecified.
"""

from __future__ import annotations

import re
from itertools import pairwise

from esolangs._drive import drive
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
    rotated = ((value >> 1) | (value << (width - 1))) & mask
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
        raise HaltError(
            "incomplete INTERCAL expression",
            hint="supply a complete INTERCAL operand or expression",
        )
    if text[at] in "'\"":
        delimiter = text[at]
        at += 1
        while at < len(text) and text[at].isspace():
            at += 1
        # A program truncated right after its delimiter leaves nothing to
        # read here; the entry guard above cannot see it, because `at` was
        # in range when this call began.
        if at >= len(text):
            raise HaltError(
                "incomplete INTERCAL expression",
                hint="supply a complete INTERCAL operand or expression",
            )
        unary = text[at] if text[at] in "&V?" else ""
        at += bool(unary)
        (left, width), at = _expression(text, variables, at)
        while at < len(text) and text[at].isspace():
            at += 1
        if at < len(text) and text[at] in "$~":
            operator = text[at]
            (right, right_width), at = _expression(text, variables, at + 1)
            if operator == "$":
                if not 0 <= left <= 65535 or not 0 <= right <= 65535:
                    raise HaltError(
                        "INTERCAL mingle needs two onespot values",
                        hint="use two 16-bit onespot values as mingle operands",
                    )
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
                width = right_width
        while at < len(text) and text[at].isspace():
            at += 1
        if at >= len(text) or text[at] != delimiter:
            raise HaltError(
                "unbalanced INTERCAL expression group",
                hint="balance the expression grouping marks",
            )
        return ((_unary(left, width, unary) if unary else left), width), at + 1
    match = re.match(r"([.#])([&V?]?)([0-9]+)", text[at:])
    if match is None:
        raise HaltError(
            "invalid INTERCAL operand",
            hint="use an INTERCAL constant, variable or grouped expression",
        )
    sigil, unary, number = match.groups()
    number = number.lstrip("0") or "0"
    if len(number) > 5 or int(number) > 65535:
        raise HaltError("INTERCAL operand out of range")
    value = int(number)
    if sigil == ".":
        if value == 0:
            raise HaltError("invalid INTERCAL variable number")
        value = variables.get(value, 0)
    if unary:
        value = _unary(value, 16, unary)
    return (value, 16), at + len(match[0])


def _roman(value: int) -> str:
    """Return Roman output; emit a separate overbar line when needed."""
    if not 0 <= value < 2**32:
        raise HaltError("INTERCAL output out of range")
    chunks: list[tuple[str, str]] = []
    place = 0
    while value:
        value, digit = divmod(value, 10)
        group, column = divmod(place, 3)
        one, five, ten = ("IVX", "XLC", "CDM")[column]
        if column == 0 and group and digit <= 3:
            text = "M" * digit
            group -= 1
        elif digit <= 3:
            text = one * digit
        elif digit == 4:
            text = one + five
        elif digit <= 8:
            text = five + one * (digit - 5)
        else:
            text = one + ten
        if group >= 2:
            text = text.lower()
        chunks.append((text, ("_" if group % 2 else " ") * len(text)))
        place += 1
    body = "".join(text for text, _bars in reversed(chunks))
    bars = "".join(bars for _text, bars in reversed(chunks))
    # Keep the repository's empty zero and ordinary single-line output.
    return bars + "\n" + body if "_" in bars else body


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


def _variable(token: str) -> int:
    match = re.fullmatch(r"\.([0-9]+)", token)
    if match is None:
        raise HaltError("invalid INTERCAL variable")
    number = match[1].lstrip("0") or "0"
    if len(number) > 5 or not 1 <= int(number) <= 65535:
        raise HaltError("invalid INTERCAL variable number")
    return int(number)


class _Machine:
    """Parsed INTERCAL statements, variables, and NEXT stack."""

    def __init__(self, code: str, io: IO) -> None:
        self.io = io
        self._input_reads = 0
        self.lines = _statements(code)
        polite = sum(
            bool(re.match(r"(?:\(\d+\)\s+)?PLEASE", line)) for line in self.lines
        )
        if (
            not self.lines
            or polite * 5 < len(self.lines)
            or polite * 3 > len(self.lines)
        ):
            raise HaltError(
                "INTERCAL program is insufficiently or excessively polite",
                hint="use PLEASE on one fifth to one third of the statements",
            )
        self.labels: dict[int, int] = {}
        for i, line in enumerate(self.lines):
            found = re.match(r"\((\d+)\)", line)
            if found:
                number = found.group(1).lstrip("0") or "0"
                if len(number) > 5 or not 1 <= int(number) <= 65535:
                    raise HaltError("invalid INTERCAL label number")
                label = int(number)
                if label in self.labels:
                    raise HaltError(f"duplicate INTERCAL label: {label}")
                self.labels[label] = i
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
        return (
            *self.state,
            self.io.position(),
            self._input_reads,
            tuple(self.lines),
            tuple(sorted(self.labels.items())),
        )

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
                raise HaltError(
                    "invalid INTERCAL calculation",
                    hint="use a valid INTERCAL expression as the assignment value",
                )
            name = _variable(target)
            if not 0 <= value <= 65535:
                raise HaltError("INTERCAL onespot assignment overflow")
            variables[name] = value
        elif line.startswith("READ OUT "):
            (value, _width), end = _expression(line[9:], variables)
            if end != len(line[9:]):
                raise HaltError(
                    "invalid INTERCAL output expression",
                    hint="give READ OUT a valid numeric expression",
                )
            self.io.print_str(_roman(value) + "\n")
        elif line.startswith("WRITE IN ."):
            name = _variable(line[9:])
            line_in = self.io.input_str()
            self._input_reads += 1
            words = line_in.upper().split()
            if not words or any(word not in _DIGITS for word in words):
                raise HaltError(
                    "invalid INTERCAL numeric input",
                    hint="supply decimal numeric input",
                )
            value = 0
            for word in words:
                value = value * 10 + int(_DIGITS[word])
                if value > 65535:
                    raise HaltError("INTERCAL onespot input overflow")
            variables[name] = value
        elif line.endswith(" NEXT") and line.startswith("("):
            label = int(line[1 : line.index(")")])
            if len(stack) >= 80:
                raise HaltError("INTERCAL NEXT stack overflow")
            if label not in self.labels:
                raise HaltError(f"unknown INTERCAL label: {label}")
            stack = (*stack, ind)
            ind = self.labels[label]
        elif line.startswith(("RESUME ", "FORGET ")):
            command, source = line.split(" ", 1)
            (count, _width), end = _expression(source, variables)
            if end != len(source) or (command == "RESUME" and count == 0):
                raise HaltError(
                    "invalid INTERCAL stack count", hint="use a nonnegative stack count"
                )
            if command == "RESUME":
                if count > len(stack):
                    raise HaltError(
                        "INTERCAL NEXT stack underflow",
                        hint="leave enough stack entries for the operation to consume",
                    )
                ind = stack[-count]
            stack = stack[: max(0, len(stack) - count)]
        elif line == "GIVE UP":
            ind = len(self.lines)
        else:
            raise HaltError(
                f"unsupported INTERCAL statement: {line}",
                hint="use statements supported by esolangs describe --spec INTERCAL",
            )
        self.state = (ind, tuple(sorted(variables.items())), stack)


def run(code: str, io: IO) -> None:
    """Execute an INTERCAL program."""
    machine = _Machine(code, io)
    drive(machine)


if __name__ == "__main__":
    script_main(run)
