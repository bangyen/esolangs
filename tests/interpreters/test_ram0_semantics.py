"""Independent scanner and dictionary RAM; esolangs.org/wiki/RAM0."""

import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.ram0 import _Machine, run


def parse(code):
    tokens = []
    pos = 0
    while pos < len(code):
        char = code[pos]
        if char in "ZANCLS":
            tokens.append(char)
        elif char in "123456789":
            end = pos + 1
            while end < len(code) and code[end].isdecimal():
                end += 1
            tokens.append(code[pos:end])
            pos = end
            continue
        pos += 1
    return tokens


def dump(z, n, ram):
    entries = ",\n".join(f"    {address}: {value}" for address, value in ram.items())
    block = "{\n" + entries + "\n}" if entries else "{}"
    return f"z: {z}\nn: {n}\nram: {block}"


def reference(code, cap):
    tokens = parse(code)
    ram = {}
    pc = z = n = 0
    for _ in range(cap):
        if pc >= len(tokens):
            break
        command = tokens[pc]
        following = pc + 1
        if command == "Z":
            z = 0
        elif command == "A":
            z += 1
        elif command == "N":
            n = z
        elif command == "L":
            z = ram.get(z, 0)
        elif command == "S":
            ram[n] = z
        elif command == "C":
            if z == 0:
                following += 1
        else:
            following = int(command) - 1
        pc = following
    halted = pc >= len(tokens)
    return dump(z, n, ram) if halted else "", z, n, tuple(ram.items()), pc, halted


def observe(code, cap):
    io = ScriptedIO("unused")
    machine = _Machine(code, io)
    assert machine.dumped is False
    assert machine.tokens == parse(code)
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
    assert io.getvalue() == ""
    assert io.position() == 0
    assert machine.stack == []
    assert machine.ind == machine.ip
    assert machine.memory == [
        machine.z,
        machine.n,
        *(value for _, value in sorted(machine.ram.items())),
    ]
    if machine.halted:
        snapshot = machine.snapshot()
        machine.step()
        output = io.getvalue()
        assert machine.dumped is True
        machine.step()
        machine.step()
        assert io.getvalue() == output
        assert machine.snapshot() == snapshot
    return (
        io.getvalue(),
        machine.z,
        machine.n,
        tuple(machine.ram.items()),
        machine.ip,
        machine.halted,
    )


def corpus():
    for size in range(4):
        for tokens in itertools.product("ZANCLS129", repeat=size):
            yield " ".join(tokens)
    yield from [
        "",
        " \n\t ",
        "A /* comment */ A // another comment A",
        "A A 0 A",
        "A 999 A",
        "A 012 A",
        "A -3 A A",
        "A 1٩ A",
        "٩A²A",
        "A N S L",
        "A Z C A A",
        "A A N A A A S A A L",
        "A N A S A A N A A S",
        "A N A S A A A N S",
        "A A A N S A A A N S A A A N S",
        "A A A A A N A A A S A A A A A N L",
        "A A N A A A S A A A N A A A A S A A L A A A L",
        "A N S A A N S A A A N S A A A A N S A A A A A N S",
        "A invalid B C D E F G H I J K L M O P Q R T U V W X Y Z",
        "ANAS" * 80,
        "AS" * 80,
        "AANASZNASZANAS",
        "ASZ1",
        "Z1",
    ]
    rng = random.Random(1713)
    for _ in range(32):
        yield " ".join(rng.choices([*"ZANCLS", "1", "2", "9", "21"], k=20))


@pytest.mark.parametrize("cap", [0, 1, 2, 9, 400])
def test_bounded_states_match_independent_dictionary(cap):
    for code in corpus():
        assert observe(code, cap) == reference(code, cap), (code, cap)


def test_run_matches_proven_halting_reference():
    for code in corpus():
        result = reference(code, 400)
        if result[-1]:
            io = ScriptedIO("unused")
            run(code, io)
            assert io.getvalue() == result[0], code
            assert io.position() == 0


@pytest.mark.parametrize(
    ("code", "z", "n", "ram"),
    [
        ("AAAZ", 0, 0, {}),
        ("AAA", 3, 0, {}),
        ("AAAN", 3, 3, {}),
        ("AANAAAS", 5, 2, {2: 5}),
        ("C A", 0, 0, {}),
        ("A C A", 2, 0, {}),
        ("A 3 A A", 3, 0, {}),
        ("ANASAS", 3, 1, {1: 3}),
        ("ANSL", 1, 1, {1: 1}),
        ("AANASZNASZANAS", 2, 1, {2: 3, 0: 1, 1: 2}),
        ("AANAAAS AAL", 0, 2, {2: 5}),
        ("AAANAA", 5, 3, {}),
        ("AAANA", 4, 3, {}),
        ("A 999 A", 1, 0, {}),
    ],
)
def test_reference_positive_controls(code, z, n, ram):
    result = reference(code, 400)
    assert result[-1]
    assert result[:4] == (dump(z, n, ram), z, n, tuple(ram.items()))
    assert observe(code, 400) == result


def test_snapshot_distinguishes_store_at_equal_registers_and_cursor():
    machine = _Machine("ASZ1", ScriptedIO())
    before = machine.snapshot()
    for _ in range(4):
        machine.step()
    assert (machine.ip, machine.z, machine.n) == (0, 0, 0)
    assert machine.ram == {0: 1}
    assert machine.snapshot() != before
    assert observe("Z1", 80) == ("", 0, 0, (), 0, False)
    assert observe("ANAS1", 80) == reference("ANAS1", 80)


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("width", [None, 1])
def test_every_small_generated_table_in_independent_engine(n, width):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        template = esolangs.generate("RAM0", table, width=width)
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            code = esolangs.instantiate("RAM0", template, bits)
            result = reference(code, 10_000)
            assert result[-1], (table, row, width)
            assert result[1] == int(answer), (table, row, width)
            assert observe(code, 10_000) == result, (table, row, width)
            io = ScriptedIO("unused")
            run(code, io)
            assert io.getvalue() == result[0]
            assert io.position() == 0


def test_run_uses_supplied_io_and_exact_dump():
    io = ScriptedIO("unused")
    run("ANS", io)
    assert io.getvalue() == "z: 1\nn: 1\nram: {\n    1: 1\n}"
    assert io.position() == 0
