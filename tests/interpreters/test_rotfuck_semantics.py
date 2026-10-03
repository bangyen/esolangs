"""Literal source rotation and mutable tape, with independent dynamic seeks."""

import itertools
import random

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.rotfuck import _Machine, run
from esolangs.tools.rotfuck import rotfuck


class Reference:
    def __init__(self, code, stdin):
        self.text = code
        self.stdin = stdin
        self.offset = self.pc = self.pointer = self.turns = 0
        self.cells = [0]
        self.output = ""

    def rotate(self):
        self.text = self.text.translate(str.maketrans("+-><,.[]", "-><,.[]+"))
        self.turns += 1

    def seek(self, direction):
        opening, closing = ("[", "]") if direction == 1 else ("]", "[")
        level = 1
        index = self.pc + direction
        while 0 <= index < len(self.text):
            char = self.text[index]
            level += (char == opening) - (char == closing)
            if not level:
                return index
            index += direction
        raise HaltError(f"an executed {opening!r} has no bracket partner")

    def step(self):
        if self.pc >= len(self.text):
            return
        char = self.text[self.pc]
        cell = self.cells[self.pointer]
        target = None
        if char == "+":
            self.cells[self.pointer] = (cell + 1) % 256
        elif char == "-":
            self.cells[self.pointer] = (cell - 1) % 256
        elif char == ">":
            self.pointer += 1
            if self.pointer == len(self.cells):
                self.cells.append(0)
        elif char == "<":
            self.pointer = max(0, self.pointer - 1)
        elif char == ",":
            if self.offset == len(self.stdin):
                raise EOFError
            self.cells[self.pointer] = ord(self.stdin[self.offset]) % 256
            self.offset += 1
        elif char == ".":
            self.output += chr(cell)
        fires = (char == "[" and not cell) or (char == "]" and cell)
        if char in "+-><,.[]":
            self.rotate()
        if fires:
            target = self.seek(1 if char == "[" else -1)
        self.pc = (self.pc if target is None else target) + 1


def compare(code, stdin="", cap=40):
    ref = Reference(code, stdin)
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    for step in range(cap + 1):
        assert (machine.tape, machine.ptr, machine.ind, machine.prog.rotation()) == (
            tuple(ref.cells),
            ref.pointer,
            ref.pc,
            ref.turns,
        ), (
            code,
            step,
        )
        assert machine.snapshot() == (
            ref.turns,
            tuple(ref.cells),
            ref.pointer,
            ref.pc,
            ref.offset,
        )
        if len(code) < 100:
            assert "".join(machine.prog.at(i) for i in range(len(code))) == ref.text
        elif ref.pc < len(code):
            assert machine.prog.at(ref.pc) == ref.text[ref.pc]
        assert io.getvalue() == ref.output
        assert machine.memory == ref.cells
        assert machine.ip == ref.pc
        assert machine.stack == []
        if machine.halted:
            before = machine.snapshot()
            machine.step()
            assert machine.snapshot() == before
            return "halt", ref
        if step == cap:
            return "bounded", ref
        before = (machine.tape, machine.ptr, machine.ind, machine.prog.rotation())
        hashed = hash(before)
        failure = None
        try:
            ref.step()
        except (EOFError, HaltError) as error:
            failure = (type(error), str(error))
        if failure:
            kind, message = failure
            with pytest.raises(kind) as actual:
                machine.step()
            if kind is HaltError:
                assert str(actual.value) == message
                ref.error = message
            assert (
                machine.tape,
                machine.ptr,
                machine.ind,
                machine.prog.rotation(),
            ) == (tuple(ref.cells), ref.pointer, ref.pc, ref.turns)
            assert io.position() == ref.offset
            assert io.getvalue() == ref.output
            assert hash(before) == hashed
            return kind.__name__, ref
        machine.step()
        assert hash(before) == hashed
    raise AssertionError("negative cap")


def public(code, stdin, status, ref):
    if status == "bounded":
        return
    io = ScriptedIO(stdin)
    if status == "halt":
        run(code, io)
    else:
        kind = EOFError if status == "EOFError" else HaltError
        with pytest.raises(kind) as actual:
            run(code, io)
        if kind is HaltError:
            assert str(actual.value) == ref.error
    assert io.position() == ref.offset
    assert io.getvalue() == ref.output


@pytest.mark.medium
@pytest.mark.parametrize("length", range(6))
@pytest.mark.parametrize("stdin", ["", "\0", "A\nĀ😀"])
def test_bounded_short_source_corpus(length, stdin):
    for chars in itertools.product("+-><,.[]x", repeat=length):
        source = "".join(chars)
        status, ref = compare(source, stdin)
        public(source, stdin, status, ref)


@pytest.mark.medium
@pytest.mark.parametrize("seed", range(8))
def test_seeded_sources_and_unicode_input(seed):
    rng = random.Random(101806 + seed)
    for _ in range(500):
        code = "".join(
            rng.choice("+-><,.[] abcé😀") for _ in range(rng.randrange(1, 101))
        )
        stdin = "".join(
            chr(rng.choice((0, 1, 10, 127, 128, 255, 256, 257, 0x1F600)))
            for _ in range(rng.randrange(15))
        )
        status, ref = compare(code, stdin, cap=200)
        public(code, stdin, status, ref)


def encode(commands):
    cycle = "+-><,.[]"
    return "".join(
        cycle[(cycle.index(command) - turn) % 8]
        for turn, command in enumerate(commands)
    )


@pytest.mark.parametrize(
    ("commands", "stdin", "output"),
    [
        ("+" * 256 + ".", "", "\0"),
        ("-.--.", "", "\xff\xfd"),
        (">++>>.<.<.", "", "\0\0\2"),
        ("<<+.", "", "\1"),
        (",>,<.>.", "A\n", "A\n"),
        (",.", "Ā", "\0"),
        (",+.", "😀", "\1"),
    ],
)
def test_positive_linear_controls(commands, stdin, output):
    source = encode(commands)
    status, expected = compare(source, stdin, cap=1000)
    assert status == "halt"
    assert expected.output == output
    io = ScriptedIO(stdin)
    run(source, io)
    assert io.getvalue() == output
    assert io.position() == expected.offset


@pytest.mark.parametrize(
    ("source", "stdin", "output"),
    [
        (",,", "A", "A"),
        ("+<.]>", "x\0", ""),
        ("[[.].]", "", ""),
        ("<+..>[]", "\0", "\1"),
    ],
)
def test_positive_dynamic_seek_controls(source, stdin, output):
    status, expected = compare(source, stdin, cap=1000)
    assert status == "halt"
    assert expected.output == output
    io = ScriptedIO(stdin)
    run(source, io)
    assert io.getvalue() == output


def generated(table, indices):
    source = rotfuck(table)
    n = (len(table) - 1).bit_length()
    for row in sorted(set(indices)):
        stdin = format(row, f"0{n}b")
        status, expected = compare(source, stdin, cap=200000)
        assert status == "halt"
        assert expected.output == table[row]
        assert expected.offset == n
        io = ScriptedIO(stdin)
        run(source, io)
        assert io.getvalue() == table[row]
        assert io.position() == n


@pytest.mark.slow
@pytest.mark.parametrize("n", [1, 2, 3])
def test_generated_all_small_tables(n):
    for value in range(1 << (1 << n)):
        generated(format(value, f"0{1 << n}b"), range(1 << n))


@pytest.mark.slow
@pytest.mark.parametrize(("n", "count"), [(4, 8), (5, 4)])
def test_generated_seeded_dense_sparse_and_constants(n, count):
    rng = random.Random(101806 + n)
    size = 1 << n
    tables = [
        "0" * size,
        "1" * size,
        "".join(str(row.bit_count() & 1) for row in range(size)),
    ]
    tables += ["".join(rng.choice("01") for _ in range(size)) for _ in range(count)]
    tables += [
        "".join(str(int(row == point)) for row in range(size))
        for point in (0, size // 2, size - 1)
    ]
    for table in tables:
        generated(table, range(size))


@pytest.mark.slow
@pytest.mark.parametrize("n", [6, 7, 8])
def test_generated_radix_boundary(n):
    size = 1 << n
    table = "".join(str(row.bit_count() & 1) for row in range(size))
    indices = (
        range(size)
        if n == 6
        else [
            0,
            size - 1,
            size // 2 - 1,
            size // 2,
            *[1 << bit for bit in range(n)],
            *[size - 1 - (1 << bit) for bit in range(n)],
        ]
    )
    generated(table, indices)


@pytest.mark.medium
@pytest.mark.parametrize("n", [10, 12, 17])
def test_generated_pruned_inputs_and_boundary_bits(n):
    size = 1 << n
    indices = [
        0,
        size - 1,
        size // 2 - 1,
        size // 2,
        *[1 << bit for bit in range(n)],
        *[size - 1 - (1 << bit) for bit in range(n)],
    ]
    for table in (
        "0" * size,
        "1" * size,
        "".join(str((row >> (n - 1)) ^ (row & 1)) for row in range(size)),
    ):
        generated(table, indices)
