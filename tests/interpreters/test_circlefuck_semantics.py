"""Independent byte escapes and identity-based ring; wiki revision 156668."""

import itertools
import random
import re

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.circlefuck import _Machine, parse


@pytest.mark.parametrize("value", range(256))
def test_all_byte_escape_spellings(value):
    for source in (
        f"\\{value:03d}",
        f"\\o{value:03o}",
        f"\\x{value:02x}",
        f"\\x{value:02X}",
    ):
        assert parse(source) == decode(source) == [value]
        assert parse("A" + source + "Z") == [65, value, 90]
    if value < 16:
        assert parse("\\" + f"{value:X}") == [value]
    if 33 <= value <= 126 and value != 92:
        assert parse(chr(value)) == [value]


def test_named_escapes_and_nonprintable_filter():
    for spelling, value in (
        ("space", 32),
        (" ", 32),
        ("n", 10),
        ("r", 13),
        ("t", 9),
        ("b", 8),
        ("\\", 92),
    ):
        assert parse("\\" + spelling) == decode("\\" + spelling) == [value]
    for value in range(512):
        char = chr(value)
        if value == 92:
            continue
        assert parse(char) == ([value] if 33 <= value <= 126 else [])
    assert parse("\\0 00") == [0, 48, 48]
    assert parse("\\12") == [1, 50]
    assert parse("\\1٢3") == [1, 51]


@pytest.mark.parametrize("base", [8, 10])
def test_out_of_byte_range_escapes_are_rejected(base):
    for value in range(256, 512 if base == 8 else 1000):
        source = f"\\o{value:03o}" if base == 8 else f"\\{value:03d}"
        with pytest.raises(ValueError, match="invalid Circlefuck escape"):
            parse(source)
        with pytest.raises(ValueError, match="invalid Circlefuck escape"):
            decode(source)


@pytest.mark.parametrize(
    "source",
    [
        "\\",
        "\\x",
        "\\x0",
        "\\xG0",
        "\\o",
        "\\o00",
        "\\o008",
        "\\q",
        "\\a",
        "\\f",
        "\\١٢٣",
        "\\\uff11\uff12\uff13",
        "\\²",
    ],
)
def test_malformed_and_nonascii_escape_digits(source):
    with pytest.raises(ValueError, match="invalid Circlefuck escape"):
        parse(source)
    with pytest.raises(ValueError, match="invalid Circlefuck escape"):
        decode(source)


class Ring:
    def __init__(self, values, ip=0, ptr=0, stdin=""):
        self.stdin = stdin
        self.consumed = 0
        self.past_end = 0
        self.nodes = [[value] for value in values]
        self.ip = self.nodes[ip]
        self.ptr = self.nodes[ptr]
        self.done = False
        self.output = ""

    def index(self, node):
        return next(i for i, n in enumerate(self.nodes) if n is node)

    def next(self, node, delta=1):
        return self.nodes[(self.index(node) + delta) % len(self.nodes)]

    def state(self):
        return (
            tuple(n[0] for n in self.nodes),
            self.index(self.ip),
            self.index(self.ptr),
            self.done,
            self.output,
        )

    def snapshot(self):
        cells, ip, ptr, done, _ = self.state()
        return cells, ip, ptr, self.consumed, done

    def step(self):
        if self.done:
            return
        command = chr(self.ip[0])
        if command == ">":
            self.ptr = self.next(self.ptr)
        elif command == "<":
            self.ptr = self.next(self.ptr, -1)
        elif command == "+":
            self.ptr[0] = (self.ptr[0] + 1) & 255
        elif command == "-":
            self.ptr[0] = (self.ptr[0] - 1) & 255
        elif command == ".":
            self.output += chr(self.ptr[0])
        elif command == ",":
            if self.consumed == len(self.stdin):
                self.past_end += 1
            else:
                self.ptr[0] = ord(self.stdin[self.consumed]) & 255
                self.consumed += 1
        elif command == "@":
            self.done = True
            return
        elif command == "#":
            self.ip = self.next(self.ip)
        elif command == "{":
            new = [0]
            self.nodes.insert(self.index(self.ptr), new)
            self.ptr = new
        elif command == "}":
            if len(self.nodes) == 1:
                raise HaltError(
                    "'}' deletes the current cell and this is the last one, "
                    "so there would be no program left to run"
                )
            deleted = self.ptr
            following = self.next(deleted)
            if self.ip is deleted:
                self.ip = following
            self.ptr = following
            self.nodes.pop(self.index(deleted))
        elif (command == "[" and self.ptr[0] == 0) or (
            command == "]" and self.ptr[0] != 0
        ):
            delta = 1 if command == "[" else -1
            current = self.ip
            depth = 1
            while True:
                current = self.next(current, delta)
                if current is self.ip:
                    return
                depth += (current[0] == ord(command)) - (
                    current[0] == ord("]" if command == "[" else "[")
                )
                if not depth:
                    break
            self.ip = current
        self.ip = self.next(self.ip)


def observe(actual):
    assert actual.ip == actual.ind
    assert actual.memory == list(actual.cells)
    assert actual.stack == []
    assert actual.state == (actual.ind, actual.ptr, actual.cells, actual.halted)
    return actual.snapshot(), actual.halted, actual.io.getvalue(), actual.io.past_end


def compare_values(values, stdin="", cap=24, ip=0, ptr=0):
    source = "".join(f"\\{value:03d}" for value in values)
    actual = _Machine(source, ScriptedIO(stdin))
    actual._ind, actual._ptr = ip, ptr  # noqa: SLF001
    expected = Ring(values, ip, ptr, stdin)
    visited = set()
    for step in range(cap + 1):
        assert observe(actual) == (
            expected.snapshot(),
            expected.done,
            expected.output,
            expected.past_end,
        )
        if expected.done:
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
        old_state = actual.state
        fingerprint = hash(frozen)
        try:
            expected.step()
        except HaltError:
            with pytest.raises(HaltError, match="this is the last one"):
                actual.step()
            assert actual.state == old_state
            return expected, "error"
        actual.step()
        assert hash(frozen) == fingerprint
        assert isinstance(old_state[2], tuple)
    raise AssertionError("unreachable")


@pytest.mark.medium
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 24])
@pytest.mark.parametrize("stdin", ["", "01", "\x00\xff\u0101"])
def test_exhaustive_ring_execution(cap, stdin):
    for length in range(1, 4):
        for chars in itertools.product("><+-.,[]@#{}x", repeat=length):
            compare_values(list(map(ord, chars)), stdin, cap)


@pytest.mark.medium
@pytest.mark.parametrize("command", list("><+-.,[]@#{}x"))
def test_seeded_ring_edits_brackets_and_byte_inputs(command):
    for size in range(1, 5):
        for fill, ip, ptr in itertools.product(
            (0, 1, 91, 93, 255), range(size), range(size)
        ):
            values = [fill] * size
            values[ip] = ord(command)
            for stdin in ("", "\x00\xff\u0101"):
                compare_values(values, stdin, ip=ip, ptr=ptr)


def test_snapshot_distinguishes_halted_state():
    machine = _Machine("@", ScriptedIO())
    before = machine.snapshot()
    assert not machine.halted
    machine.step()
    assert machine.halted
    assert machine.snapshot() != before


@pytest.mark.medium
def test_published_hello_quine_cat_and_truth_machine():
    hello = [
        *map(ord, "<[.<]@"),
        0,
        10,
        *map(ord, "!dlroW"),
        32,
        *map(ord, ",olleH"),
    ]
    result, verdict = compare_values(hello, cap=1000)
    assert verdict == "halt"
    assert result.output == "Hello, World!\n"
    source = "{>[.>]@"
    result, verdict = compare_values(list(map(ord, source)), cap=1000)
    assert verdict == "halt"
    assert result.output == source
    for stdin in ("", "Hello\n", "\xff\u0101"):
        result, verdict = compare_values(list(map(ord, "{,[.[-],]@")), stdin, cap=3000)
        assert verdict == "halt"
        assert result.output == "".join(chr(ord(char) & 255) for char in stdin)
        assert result.consumed == len(stdin)
    source = "," + "-" * 48 + "[[-]" + "+" * 49 + ".]" + "+" * 48 + ".@"
    result, verdict = compare_values(list(map(ord, source)), "0", cap=1000)
    assert verdict == "halt"
    assert result.output == "0"
    result, verdict = compare_values(list(map(ord, source)), "1", cap=3000)
    assert verdict == "cycle"
    assert result.output
    assert set(result.output) == {"1"}


def decode(source):
    pattern = re.compile(
        r"\\(?:space|[ nrtb\\]|o[0-7]{3}|x[0-9a-fA-F]{2}|[0-9]{3}|[0-9A-F])|[^\\]"
    )
    result = []
    position = 0
    while position < len(source):
        match = pattern.match(source, position)
        if not match:
            raise ValueError("invalid Circlefuck escape")
        token = match.group()
        position = match.end()
        if len(token) == 1:
            if 33 <= ord(token) <= 126:
                result.append(ord(token))
        else:
            tail = token[1:]
            if tail in ("space", " ", "n", "r", "t", "b", "\\"):
                value = {
                    "space": 32,
                    " ": 32,
                    "n": 10,
                    "r": 13,
                    "t": 9,
                    "b": 8,
                    "\\": 92,
                }[tail]
            elif tail.startswith("o"):
                value = int(tail[1:], 8)
            elif tail.startswith("x"):
                value = int(tail[1:], 16)
            else:
                value = int(tail, 10 if len(tail) == 3 else 16)
            if value > 255:
                raise ValueError("invalid Circlefuck escape")
            result.append(value)
    return result


def run_generated(source, stdin, output, cap=100000):
    expected = Ring(decode(source), stdin=stdin)
    actual = _Machine(source, ScriptedIO(stdin))
    assert actual.cells == tuple(node[0] for node in expected.nodes)
    for _ in range(cap):
        if expected.done:
            break
        expected.step()
        actual.step()
    assert expected.done
    assert observe(actual) == (
        expected.snapshot(),
        True,
        expected.output,
        expected.past_end,
    )
    assert expected.output == output
    return expected


@pytest.mark.medium
@pytest.mark.parametrize(("n", "batch"), [(1, 0), (2, 0), *[(3, i) for i in range(8)]])
@pytest.mark.parametrize("width", [None, 1, 7, 80])
def test_generated_all_small_tables(n, batch, width):
    for value in range(batch * 32, min(batch * 32 + 32, 1 << (1 << n))):
        table = f"{value:0{1 << n}b}"
        source = esolangs.generate("Circlefuck", table, width=width)
        for row, answer in enumerate(table):
            stdin = f"{row:0{n}b}"
            expected = run_generated(source, stdin, answer)
            assert expected.consumed == n
            assert esolangs.run("Circlefuck", source, stdin) == answer


@pytest.mark.medium
@pytest.mark.parametrize("values", [[0, 255], [48, 49, 50, 51], [0, 92, 123, 255]])
def test_generated_arbitrary_bytes(values):
    from esolangs.tools.circlefuck import _circlefuck_table

    n = (len(values) - 1).bit_length()
    source = _circlefuck_table(values)
    for row, value in enumerate(values):
        expected = run_generated(source, f"{row:0{n}b}", chr(value))
        assert expected.consumed == n


@pytest.mark.medium
@pytest.mark.parametrize("row", [0, 127, 128, 129, 255, 256, 257, 383, 384, 511])
def test_generated_nine_input_carry_boundaries(row):
    table = "".join("1" if index % 3 == 0 else "0" for index in range(512))
    source = esolangs.generate("Circlefuck", table)
    expected = run_generated(source, f"{row:09b}", table[row])
    assert expected.consumed == 9


@pytest.mark.medium
@pytest.mark.parametrize(
    "stdin", ["", "1\n", "x\ny\nz\n", "9\n9\n9\n", "\u0101\x00\xff"]
)
def test_generated_outside_alphabet_and_eof(stdin):
    table = "01101001"
    consumed = min(3, len(stdin))
    bits = [int((ord(stdin[i]) & 255) != 48) if i < consumed else 1 for i in range(3)]
    row = sum(bit << (2 - i) for i, bit in enumerate(bits))
    expected = run_generated(esolangs.generate("Circlefuck", table), stdin, table[row])
    assert expected.consumed == consumed
    assert expected.past_end == 3 - consumed


@pytest.mark.slow
@pytest.mark.parametrize("n", [10, 11, 12])
def test_generated_programs_used_for_size_growth(n):
    randomizer = random.Random(11)
    for arity in (10, 11, 12):
        table = "".join(randomizer.choice("01") for _ in range(1 << arity))
        if arity == n:
            break
    source = esolangs.generate("Circlefuck", table)
    for row in (0, 1, (1 << (n - 1)) - 1, 1 << (n - 1), (1 << n) - 1):
        expected = run_generated(source, f"{row:0{n}b}", table[row])
        assert expected.consumed == n


def test_empty_decoded_program_is_rejected():
    for source in ("", " \n\t", "\u0101"):
        assert decode(source) == []
        with pytest.raises(ValueError, match=r"^Circlefuck program cannot be empty$"):
            _Machine(source, ScriptedIO())


@pytest.mark.medium
def test_every_byte_outside_command_set_is_inert():
    for value in range(256):
        expected, verdict = compare_values([value, 46, 64], cap=20)
        if chr(value) not in "><+-.,[]@#{}":
            assert verdict == "halt"
            assert expected.output == chr(value)
