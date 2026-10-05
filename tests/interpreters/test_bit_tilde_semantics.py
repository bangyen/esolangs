"""Mutable sparse bits, a separate pool extent, and lexical brace pairs."""

import itertools
import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.bit_tilde import _Machine, run
from esolangs.tools.bit_tilde import bit_tilde
from tests.interpreters.views import view as vm_view


class Reference:
    def __init__(self, code, stdin):
        self.code = code
        self.stdin = stdin
        self.pc = self.ptr = self.offset = 0
        self.extent = 8
        self.bits = {}
        self.output = ""
        self.pairs = {}
        stack = []
        for i, char in enumerate(code):
            if char == "{":
                stack.append(i)
            elif char == "}" and stack:
                j = stack.pop()
                self.pairs[i] = j
                self.pairs[j] = i

    def put(self, index, value):
        if value:
            self.bits[index] = value
        else:
            self.bits.pop(index, None)

    def state(self):
        return self.pc, self.ptr, tuple(self.bits.get(i, 0) for i in range(self.extent))

    def step(self):
        if self.pc == len(self.code):
            return
        command = self.code[self.pc]
        cell = self.bits.get(self.ptr, 0)
        if command == "~":
            self.put(self.ptr, 1 - cell)
        elif command == ">":
            self.ptr += 1
            self.extent = max(self.extent, self.ptr + 7)
        elif command == "<":
            self.ptr = max(0, self.ptr - 1)
        elif command == ")":
            if self.offset == len(self.stdin):
                raise EOFError
            value = ord(self.stdin[self.offset])
            assert value < 256, "byte-domain probe only"
            self.offset += 1
            self.extent = max(self.extent, self.ptr + 8)
            for bit in range(8):
                self.put(self.ptr + bit, (value >> (7 - bit)) & 1)
        elif command == "(":
            value = 0
            for index in range(self.ptr, min(self.ptr + 8, self.extent)):
                value = value * 2 + self.bits.get(index, 0)
            self.output += chr(value)
        elif (command == "{" and cell == 0) or (command == "}" and cell != 0):
            if self.pc not in self.pairs:
                raise ValueError(f"unmatched {command!r} at position {self.pc}")
            self.pc = self.pairs[self.pc]
        self.pc += 1


def compare(code, stdin="", cap=40):
    ref = Reference(code, stdin)
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    seen = set()
    for step in range(cap + 1):
        expected = ref.state()
        assert machine.state == expected, (code, step, machine.state, expected)
        assert machine.snapshot() == (expected[2], ref.ptr, ref.pc, ref.offset)
        assert io.getvalue() == ref.output
        assert vm_view(machine, "memory") == list(expected[2])
        assert vm_view(machine, "ip") == ref.pc
        assert machine.cell == ref.ptr
        assert vm_view(machine, "stack") == []
        if machine.halted:
            old = machine.snapshot()
            machine.step()
            assert old == machine.snapshot()
            return "halt", ref
        key = (expected, ref.offset)
        if key in seen:
            return "cycle", ref
        seen.add(key)
        if step == cap:
            return "bounded", ref
        before = machine.state
        hashed = hash(before)
        failure = None
        try:
            ref.step()
        except (ValueError, EOFError) as error:
            failure = type(error), str(error)
        if failure is not None:
            kind, message = failure
            with pytest.raises(kind) as actual:
                machine.step()
            if kind is ValueError:
                assert str(actual.value) == message
            assert machine.state == before
            assert hash(before) == hashed
            assert io.getvalue() == ref.output
            assert io.position() == ref.offset
            return kind.__name__, ref
        machine.step()
        assert hash(before) == hashed
    raise AssertionError("negative execution cap")


@pytest.mark.medium
@pytest.mark.parametrize("length", range(6))
@pytest.mark.parametrize("stdin", ["", "\0", "A\n\xff"])
def test_bounded_source_corpus(length, stdin):
    for chars in itertools.product("~><)(}{x", repeat=length):
        compare("".join(chars), stdin)


@pytest.mark.medium
@pytest.mark.parametrize("seed", range(8))
def test_seeded_comment_braces_and_streams(seed):
    randomizer = random.Random(812734 + seed)
    for _ in range(200):
        code = "".join(
            randomizer.choice("~><)(}{ abcé😀")
            for _ in range(randomizer.randrange(1, 85))
        )
        stdin = "".join(
            chr(randomizer.randrange(256)) for _ in range(randomizer.randrange(12))
        )
        compare(code, stdin, cap=120)


@pytest.mark.medium
@pytest.mark.parametrize("width", [0, 1, 2, 7, 8, 9, 31, 32, 33, 63, 64, 65])
def test_every_byte_at_window_boundaries(width):
    for byte in range(256):
        compare(">" * width + ")(" + "<" * width + "(", chr(byte), cap=width * 2 + 5)


@pytest.mark.parametrize(
    ("code", "stdin", "output", "status"),
    [
        ("~(", "", "\x80", "halt"),
        (">~(", "", "@", "halt"),
        (">) (", "\xff", "\xff", "halt"),
        ("<~(", "", "\x80", "halt"),
        ("~><{(>{<~>~}~<}", "", "\x80\xc0", "halt"),
        (")()()(", "A\n\xff", "A\n\xff", "halt"),
        ("{{~~}~}(~", "", "\0", "halt"),
        ("~{", "", "", "halt"),
        ("}", "", "", "halt"),
        ("{", "", "", "ValueError"),
        ("~}", "", "", "ValueError"),
        (")", "", "", "EOFError"),
        ("~{(}", "", "\x80", "cycle"),
        ("~{>~}", "", "", "bounded"),
    ],
)
def test_positive_controls(code, stdin, output, status):
    observed, reference = compare(code, stdin)
    assert observed == status
    assert reference.output == output
    if status == "halt":
        io = ScriptedIO(stdin)
        run(code, io)
        assert io.getvalue() == output
        assert io.position() == reference.offset


def check_generated(table, indices):
    n = (len(table) - 1).bit_length()
    code = bit_tilde(table)
    for row in indices:
        stdin = format(row, f"0{n}b")
        status, reference = compare(code, stdin, cap=100000)
        assert status == "halt"
        assert reference.output == table[row]
        assert reference.offset == n
        io = ScriptedIO(stdin)
        run(code, io)
        assert io.getvalue() == reference.output
        assert io.position() == n


@pytest.mark.slow
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        check_generated(table, range(1 << n))


@pytest.mark.slow
@pytest.mark.parametrize(("n", "count"), [(4, 40), (5, 8), (6, 4)])
def test_seeded_dense_sparse_and_parity_generators(n, count):
    randomizer = random.Random(917312 + n)
    size = 1 << n
    tables = [
        "0" * size,
        "1" * size,
        "".join(str(i.bit_count() % 2) for i in range(size)),
    ]
    tables += [
        "".join(randomizer.choice("01") for _ in range(size)) for _ in range(count)
    ]
    tables += [
        "0" * position + "1" + "0" * (size - position - 1)
        for position in (0, 1, size // 2, size - 1)
    ]
    for table in tables:
        check_generated(table, range(size))


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 10, 12, 17])
def test_pruned_generators_read_ignored_inputs_and_boundary_bits(n):
    size = 1 << n
    tables = [
        "0" * size,
        "1" * size,
        "".join(str(((i >> (n - 1)) ^ i) & 1) for i in range(size)),
    ]
    indices = {0, size - 1, size // 2 - 1, size // 2, size // 2 + 1}
    for bit in range(n):
        indices.update((1 << bit, size - 1 - (1 << bit)))
    for table in tables:
        check_generated(table, sorted(indices))
