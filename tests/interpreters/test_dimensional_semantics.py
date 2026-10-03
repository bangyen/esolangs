"""Independent literal and observer checks; Dimensional wiki revision 156292."""

import itertools
import random
import re

import pytest

from esolangs.exceptions import ArgumentError, InputExhaustedError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.dimensional import _Machine


@pytest.mark.parametrize("value", range(256))
def test_character_literal_consumes_its_payload(value):
    machine = _Machine(":" + chr(value) + ".", ScriptedIO())
    machine.step()
    assert machine.ind == 2
    assert not machine.comment
    assert machine.memory == [value]
    machine.step()
    assert machine.halted
    assert machine.io.getvalue() == chr(value)


@pytest.mark.parametrize("value", range(256))
def test_two_hex_digits_set_the_byte(value):
    for spelling in (f"{value:02x}", f"{value:02X}"):
        machine = _Machine("=" + spelling + ".", ScriptedIO())
        machine.step()
        assert machine.ind == 3
        assert machine.memory == [value]
        machine.step()
        assert machine.io.getvalue() == chr(value)
        assert machine.halted


@pytest.mark.parametrize(
    "literal", [" 1", "1 ", "+1", "-1", "\uff110", "0\u0661", "gg", "[0", "}0", "**"]
)
def test_hex_literal_requires_two_ascii_hex_digits(literal):
    machine = _Machine("=" + literal + ".", ScriptedIO())
    before = machine.tape.top.freeze()
    with pytest.raises(ValueError, match="invalid hex literal") as caught:
        machine.step()
    assert str(caught.value) == f"invalid hex literal {literal!r}"
    assert machine.ind == 1
    assert machine.tape.top.freeze() == before


def test_literal_star_does_not_hide_following_loop():
    machine = _Machine(":*[-].", ScriptedIO())
    for _ in range(150):
        if machine.halted:
            break
        machine.step()
    assert machine.halted
    assert machine.io.getvalue() == "\x00"


@pytest.mark.parametrize("source", ["", "$3>0", "$4>0$2>7", "+$3>1"])
def test_memory_observer_does_not_allocate_slots(source):
    machine = _Machine(source, ScriptedIO())
    while not machine.halted:
        machine.step()
    before = machine.snapshot()
    view = machine.memory
    assert machine.snapshot() == before
    view[0] = 123
    assert machine.snapshot() == before


class FlatTape:
    def __init__(self):
        self.axis = 2
        self.height = 2
        self.nodes = {(2, ())}
        self.positions = {}
        self.bytes = {}

    def key(self, level, path):
        return tuple(
            sorted(
                ((d, v) for d, v in self.positions.get((level, path), {}).items() if v)
            )
        )

    def locate(self, level, *, allocate=True):
        if allocate:
            while self.height < level:
                self.height += 1
                self.nodes.add((self.height, ()))
        path = ()
        for ancestor in range(self.height, level, -1):
            position = self.key(ancestor, path)
            if position:
                path += ((ancestor, position),)
            if allocate:
                self.nodes.add((ancestor - 1, path))
        return path

    def value(self):
        path = self.locate(2)
        return self.bytes.setdefault((path, self.key(2, path)), 0)

    def peek(self):
        path = self.locate(2, allocate=False)
        return self.bytes.get((path, self.key(2, path)), 0)

    def set_value(self, value):
        path = self.locate(2)
        self.bytes[path, self.key(2, path)] = value & 255

    def move(self, dim, delta):
        path = self.locate(self.axis)
        coordinates = self.positions.setdefault((self.axis, path), {})
        coordinates[dim] = coordinates.get(dim, 0) + delta

    def coord(self, dim):
        path = self.locate(self.axis)
        return self.positions.get((self.axis, path), {}).get(dim, 0)

    def clear(self, dim):
        path = self.locate(self.axis)
        self.positions.get((self.axis, path), {}).pop(dim, None)

    def freeze(self, level=None, path=()):
        level = self.height if level is None else level
        if level == 2:
            slots = [
                (coordinate, value)
                for (owner, coordinate), value in self.bytes.items()
                if owner == path
            ]
        else:
            slots = []
            for child_level, child_path in self.nodes:
                if child_level != level - 1:
                    continue
                parent = child_path
                coordinate = ()
                if child_path and child_path[-1][0] == level:
                    coordinate = child_path[-1][1]
                    parent = child_path[:-1]
                if parent == path:
                    slots.append((coordinate, self.freeze(level - 1, child_path)))
        return (self.key(level, path), tuple(sorted(slots)))


class Reference:
    def __init__(self, source, stdin=""):
        self.source = source
        self.stdin = stdin
        self.position = self.reads = self.past_end = 0
        self.ip = 0
        self.comment = False
        self.output = ""
        self.tape = FlatTape()
        self.partners = {}
        pending = {"[": [], "{": []}
        tokens = re.finditer(r":[\s\S]|=[\s\S]{0,2}|\*[^*]*(?:\*|$)|[\s\S]", source)
        for token in tokens:
            text = token.group()
            index = token.start()
            if text in pending:
                pending[text].append(index)
            elif text in ("]", "}"):
                opening = "[" if text == "]" else "{"
                if not pending[opening]:
                    raise ValueError(f"unmatched {text!r} at position {index}")
                other = pending[opening].pop()
                self.partners[index] = other
                self.partners[other] = index
        for opening in ("[", "{"):
            if pending[opening]:
                raise ValueError(
                    f"unmatched {opening!r} at position {pending[opening][-1]}"
                )

    @property
    def halted(self):
        return self.ip >= len(self.source)

    def snapshot(self):
        return (
            self.ip,
            self.comment,
            self.tape.axis,
            self.tape.height,
            self.tape.freeze(),
            self.position,
        )

    def number(self, default):
        negative = self.source[self.ip : self.ip + 1] == "~"
        self.ip += negative
        digits = re.match(r"\d+", self.source[self.ip :])
        if digits is None:
            return default
        self.ip += len(digits.group())
        return int(digits.group()) * (-1 if negative else 1)

    def read_port(self, command):
        if command != ",":
            while (
                self.position < len(self.stdin) and self.stdin[self.position].isspace()
            ):
                self.position += 1
        if self.position == len(self.stdin):
            self.past_end += 1
            raise InputExhaustedError(self.position, len(self.stdin), "character")
        if command == ",":
            value = ord(self.stdin[self.position])
            self.position += 1
            self.reads += 1
            return value
        start = self.position
        while (
            self.position < len(self.stdin) and not self.stdin[self.position].isspace()
        ):
            self.position += 1
        token = self.stdin[start : self.position]
        self.reads += 1
        if command == "x":
            return int(token, 16)
        try:
            return int(token)
        except ValueError as error:
            raise ArgumentError(f"input must be an integer, got {token!r}") from error

    def step(self):
        if self.halted:
            return
        start = self.ip
        command = self.source[start]
        self.ip += 1
        if command == "*":
            self.comment = not self.comment
        elif self.comment:
            return
        elif command in "><":
            dimension = self.number(None)
            self.tape.move(
                self.tape.value() if dimension is None else dimension,
                1 if command == ">" else -1,
            )
        elif command in "+-":
            self.tape.set_value(self.tape.value() + (1 if command == "+" else -1))
        elif command == ".":
            self.output += chr(self.tape.value())
        elif command in ",dx":
            self.tape.set_value(self.read_port(command))
        elif command == ":":
            if self.ip == len(self.source):
                raise ValueError("':' must be followed by a character")
            self.tape.set_value(ord(self.source[self.ip]))
            self.ip += 1
        elif command == "=":
            if len(self.source) - self.ip < 2:
                raise ValueError("'=' must be followed by two hex digits")
            digits = self.source[self.ip : self.ip + 2]
            if re.fullmatch(r"[0-9a-fA-F]{2}", digits) is None:
                raise ValueError(f"invalid hex literal {digits!r}")
            self.tape.set_value(int(digits, 16))
            self.ip += 2
        elif command == "$":
            self.tape.axis = max(2, self.number(2))
        elif command == "[":
            if self.tape.value() == 0:
                self.ip = self.partners[start] + 1
        elif command in "]}":
            self.ip = self.partners[start]
        elif command == "{":
            dimension = self.number(0)
            if self.tape.coord(dimension) == 0:
                self.ip = self.partners[start] + 1
        elif command == "?":
            self.tape.set_value(self.tape.coord(self.number(0)))
        elif command == "!":
            self.tape.clear(self.number(0))


def inspect(actual):
    frozen = actual.snapshot()
    assert actual.memory == [actual.tape.peek_value()]
    assert actual.snapshot() == frozen
    assert actual.ip == actual.ind
    assert actual.stack == []
    return (
        frozen,
        actual.halted,
        actual.io.getvalue(),
        actual.io.reads,
        actual.io.past_end,
    )


def compare(source, stdin="", cap=24):
    malformed = None
    try:
        expected = Reference(source, stdin)
    except ValueError as error:
        malformed = str(error)
    if malformed is not None:
        with pytest.raises(ValueError, match="unmatched") as caught:
            _Machine(source, ScriptedIO(stdin))
        assert str(caught.value) == malformed
        return None, "malformed"
    actual = _Machine(source, ScriptedIO(stdin))
    visited = set()
    for step in range(cap + 1):
        assert inspect(actual) == (
            expected.snapshot(),
            expected.halted,
            expected.output,
            expected.reads,
            expected.past_end,
        )
        assert actual.memory == [expected.tape.peek()]
        if expected.halted:
            frozen = actual.snapshot()
            actual.step()
            actual.step()
            assert actual.snapshot() == frozen
            return expected, "halt"
        if expected.snapshot() in visited:
            return expected, "cycle"
        visited.add(expected.snapshot())
        if step == cap:
            return expected, "bounded"
        frozen = actual.snapshot()
        fingerprint = hash(frozen)
        error = None
        try:
            expected.step()
        except (ValueError, EOFError) as caught:
            error = caught
        if error is None:
            actual.step()
        else:
            with pytest.raises(type(error), match=r".") as caught:
                actual.step()
            assert str(caught.value) == str(error)
        assert hash(frozen) == fingerprint
        assert inspect(actual) == (
            expected.snapshot(),
            expected.halted,
            expected.output,
            expected.reads,
            expected.past_end,
        )
        if error is not None:
            return expected, "error"
    raise AssertionError("unreachable")


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
@pytest.mark.parametrize("stdin", ["", "\x00\xff\u0101", " 65\n-1 ff bad"])
def test_exhaustive_commands_comments_literals_and_ports(cap, stdin):
    for length in range(4):
        for chars in itertools.product("><+-.,dx[]{}?!$*:=", repeat=length):
            compare("".join(chars), stdin, cap)


@pytest.mark.medium
@pytest.mark.parametrize("seed", range(8))
def test_seeded_pointer_hierarchies_and_signed_dimensions(seed):
    randomizer = random.Random(3045 + seed)
    tokens = [
        "$2",
        "$3",
        "$4",
        "$5",
        "$~1",
        ">0",
        "<0",
        ">~7",
        "<~7",
        ">",
        "<",
        "?0",
        "?~7",
        "!0",
        "!~7",
        "+",
        "-",
        "=ff",
        ":A",
        ".",
        "*ignored*",
        "[+]",
    ]
    for _ in range(100):
        source = "".join(randomizer.choice(tokens) for _ in range(12))
        compare(source, cap=100)


@pytest.mark.medium
def test_nested_loops_ports_and_operand_boundaries():
    sources = [
        "=03[.-]",
        ">0>0{0<0}?0.",
        "<~7<~7{~7>~7}?~7.",
        ":*[-].",
        "$3>0+>1+<1.<0.",
        "$5>~7$3>0=41.$5<~7.",
        "+[>0+<0-]>0.",
        "=ff>?.",
        ">~x",
        "$~",
        "?~",
        "!~",
        "=",
        "=4",
        ":",
        "=g0",
        ",.d.x.",
        "d.d.",
        "x.x.",
        "*unclosed[",
        "*[}:*=41.",
        ">\u0661?\u0661.",
    ]
    for source, stdin in itertools.product(
        sources, ("", "A\n65 ff", " -257\n0xFF ", "gg", "\u0101")
    ):
        compare(source, stdin, cap=2000)


def generated_row(program, stdin, answer, reads, cap=100_000):
    expected = Reference(program, stdin)
    actual = _Machine(program, ScriptedIO(stdin))
    for machine in (expected, actual):
        for _ in range(cap):
            if machine.halted:
                break
            machine.step()
        assert machine.halted
    assert expected.output == answer
    assert expected.reads == reads
    assert inspect(actual) == (
        expected.snapshot(),
        True,
        answer,
        reads,
        expected.past_end,
    )


@pytest.mark.medium
@pytest.mark.parametrize("width", [None, 1, 3, 80])
@pytest.mark.parametrize("n", [1, 2, 3])
def test_generated_all_small_tables(n, width):
    from esolangs import generate

    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        program = generate("Dimensional", table, width)
        for row, answer in enumerate(table):
            generated_row(program, "\n".join(format(row, f"0{n}b")), answer, n)


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 6, 12])
def test_generated_larger_indices(n):
    from esolangs import generate

    table = "".join(str((row * 73 + row // 3) & 1) for row in range(1 << n))
    for width in (None, 1, 8):
        program = generate("Dimensional", table, width)
        for row in (0, 1, len(table) // 2, len(table) - 1):
            generated_row(
                program, "\n".join(format(row, f"0{n}b")), table[row], n, cap=2_000_000
            )


@pytest.mark.medium
def test_generated_sparse_twelve_input_endpoint():
    from esolangs import generate

    generated_row(
        generate("Dimensional", "0" * 4095 + "1"),
        "\n".join("1" * 12),
        "1",
        12,
        cap=2_000_000,
    )
