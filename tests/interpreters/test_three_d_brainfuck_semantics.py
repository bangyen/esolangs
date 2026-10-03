"""Mutable spatial model and inline bracket scans; wiki revision 189069."""

import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.three_d_brainfuck import _Machine


class Reference:
    def __init__(self, source, stdin=""):
        self.source = source
        self.stdin = stdin
        self.consumed = 0
        self.cells = {}
        self.array = (0, 0, 0)
        self.position = (0, 0, 0)
        self.direction = (1, 0, 0)
        self.output = ""
        pending = []
        for index, char in enumerate(source):
            if char == "[":
                pending.append(index)
            elif char == "]":
                if not pending:
                    raise ValueError(f"unmatched ']' at position {index}")
                pending.pop()
        if pending:
            raise ValueError(f"unmatched '[' at position {pending[-1]}")

    @property
    def halted(self):
        x, y, z = self.position
        return y != 0 or z != 0 or x not in range(len(self.source))

    def snapshot(self):
        return (
            tuple(sorted(self.cells.items())),
            self.array,
            self.position,
            self.direction,
            self.consumed,
        )

    def step(self):
        if self.halted:
            return
        char = self.source[self.position[0]]
        directions = {
            "n": (1, 0, 0),
            "s": (-1, 0, 0),
            "u": (0, 1, 0),
            "d": (0, -1, 0),
            "e": (0, 0, 1),
            "w": (0, 0, -1),
        }
        value = self.cells.get(self.array, 0)
        if char.lower() in directions:
            delta = directions[char.lower()]
            if char.isupper():
                self.direction = delta
            else:
                self.array = tuple(
                    a + b for a, b in zip(self.array, delta, strict=True)
                )
        elif char in "+-":
            self.cells[self.array] = (value + (1 if char == "+" else -1)) & 255
        elif char == ".":
            self.output += chr(value)
        elif char == ",":
            if self.consumed == len(self.stdin):
                raise EOFError
            self.cells[self.array] = ord(self.stdin[self.consumed]) & 255
            self.consumed += 1
        elif (char == "[" and value == 0) or (char == "]" and value != 0):
            offset = self.position[0]
            direction = 1 if char == "[" else -1
            depth = 1
            while depth:
                offset += direction
                token = self.source[offset]
                depth += (token == char) - (token == ("]" if char == "[" else "["))
            self.position = (offset + 1, 0, 0)
            return
        self.position = tuple(
            a + b for a, b in zip(self.position, self.direction, strict=True)
        )


def inspect(machine):
    assert machine.ip == (*machine.pos, *machine.heading)
    assert machine.ip_shape == "opaque"
    assert machine.memory == [value for _, value in sorted(machine.cells.items())]
    assert machine.stack == []
    return machine.snapshot(), machine.halted, machine.io.getvalue()


def compare(source, stdin="", cap=24, cells=None, array=(0, 0, 0), direction=None):
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
    if cells is not None:
        expected.cells = dict(cells)
        actual.cells = dict(cells)
    expected.array = actual.ap = array
    if direction is not None:
        expected.direction = actual.heading = direction
    visited = set()
    for _ in range(cap + 1):
        assert inspect(actual) == (
            expected.snapshot(),
            expected.halted,
            expected.output,
        )
        if expected.halted:
            frozen = actual.snapshot()
            actual.step()
            actual.step()
            assert actual.snapshot() == frozen
            return expected, "halt"
        if expected.snapshot() in visited:
            return expected, "cycle"
        visited.add(expected.snapshot())
        if len(visited) > cap:
            return expected, "bounded"
        frozen = actual.snapshot()
        fingerprint = hash(frozen)
        try:
            expected.step()
        except EOFError:
            with pytest.raises(EOFError):
                actual.step()
            assert actual.io.past_end == 1
            assert inspect(actual) == (expected.snapshot(), False, expected.output)
            return expected, "eof"
        actual.step()
        assert hash(frozen) == fingerprint
    raise AssertionError("unreachable")


def corpus():
    yield from (
        "".join(chars)
        for length in range(4)
        for chars in itertools.product("+-nsuewdNSUEWD.,x[]", repeat=length)
    )
    yield from (
        "+[]",
        "NS",
        "+NS",
        "+[n].",
        "++[-n].",
        "++[-].",
        "n[+].",
        "[[+]]",
        "[S]",
        "++[n+[s-]n-]s.",
        "^V><\"'X+.",
        "[[]",
        "][",
        "+" * 256 + ".",
        "-" * 257 + ".",
        ",.,.,.",
        ",+.-.",
    )


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
def test_exhaustive_spatial_commands_brackets_and_comments(cap):
    for source in corpus():
        compare(source, cap=cap)


@pytest.mark.medium
@pytest.mark.parametrize("command", list("+-nsuewdNSUEWD.,[]"))
def test_seeded_coordinates_headings_and_byte_edges(command):
    directions = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
    for direction, array, value in itertools.product(
        directions, ((0, 0, 0), (2, -3, 5), (-2, 4, -1)), (0, 1, 2, 254, 255)
    ):
        source = (
            "[+]." if command == "[" else "+[-]." if command == "]" else command + "."
        )
        compare(
            source,
            "\x00\n\xff\u0101",
            cells={array: value},
            array=array,
            direction=direction,
        )


@pytest.mark.medium
def test_unicode_byte_input_eof_and_snapshot_cursor():
    for stdin in ("", "A", "\n", "\x00\xff\u0101", "\U0001f600\r\n"):
        for source in (",.", ",+.-.", ",.,.,.,.", "[,.]", "n,.s."):
            compare(source, stdin, cap=40)
    machine = _Machine("+.", ScriptedIO("AB"))
    before = machine.snapshot()
    machine.io.input_char()
    assert machine.snapshot()[:-1] == before[:-1]
    assert machine.snapshot()[-1] == 1
    assert before[-1] == 0


@pytest.mark.medium
@pytest.mark.parametrize(("n", "batch"), [(1, 0), (2, 0), *[(3, i) for i in range(8)]])
def test_generated_all_small_tables(n, batch):
    from esolangs.tools.three_d_brainfuck import three_d_brainfuck

    start = batch * 32
    stop = min(start + 32, 1 << (1 << n))
    for value in range(start, stop):
        table = f"{value:0{1 << n}b}"
        source = three_d_brainfuck(table)
        for row, answer in enumerate(table):
            stdin = f"{row:0{n}b}"
            expected, verdict = compare(source, stdin, cap=20000)
            assert verdict == "halt"
            assert expected.output == answer
            assert expected.consumed == n


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6])
@pytest.mark.parametrize("kind", ["zero", "one", "single", "parity", "random"])
@pytest.mark.parametrize("width", [None, 1, 7, 80])
def test_generated_wide_tables_and_public_execution(n, kind, width):
    randomizer = random.Random(3041 + n)
    tables = {
        "zero": "0" * (1 << n),
        "one": "1" * (1 << n),
        "single": "1" + "0" * ((1 << n) - 1),
        "parity": "".join(str(row.bit_count() % 2) for row in range(1 << n)),
        "random": "".join(randomizer.choice("01") for _ in range(1 << n)),
    }
    table = tables[kind]
    source = esolangs.generate("3D Brainfuck", table, width=width)
    for row, answer in enumerate(table):
        stdin = f"{row:0{n}b}"
        expected, verdict = compare(source, stdin, cap=20000)
        assert verdict == "halt"
        assert expected.output == answer
        assert expected.consumed == n
        assert esolangs.run("3D Brainfuck", source, stdin) == answer


@pytest.mark.medium
def test_generator_paths_reach_signed_targets():
    from esolangs.tools.three_d_brainfuck import _path

    points = ((0, 0, 0), (2, -3, 5), (-2, 4, -1))
    for start, target in itertools.product(points, repeat=2):
        source = _path(start, target)
        expected, verdict = compare(source, array=start, cap=len(source) + 1)
        assert verdict == "halt"
        assert expected.array == target
