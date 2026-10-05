"""Independent word parser and two-ended bit string."""

import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.queue_based.bitdeque import _Machine, run
from tests.interpreters.views import view as vm_view


def parse(code):
    words = iter(code.split())
    tokens = []
    for word in words:
        if word in {"PUSH", "POP", "INJECT", "EJECT", "INVERT"}:
            tokens.append((word, None))
        elif word == "GOTO":
            target = next(words, "")
            if not target.isdecimal():
                raise ValueError("invalid target")
            tokens.append((word, int(target)))
        else:
            raise ValueError("invalid command")
    return tokens


def reference(code, cap):
    tokens = parse(code)
    data = ""
    reg = pc = 0
    for _ in range(cap):
        if pc >= len(tokens):
            break
        command, target = tokens[pc]
        next_pc = pc + 1
        if command == "PUSH":
            data += str(reg)
        elif command == "INJECT":
            data = str(reg) + data
        elif command == "POP":
            reg = int(data[-1]) if data else 0
            data = data[:-1]
        elif command == "EJECT":
            reg = int(data[0]) if data else 0
            data = data[1:]
        elif command == "INVERT":
            reg = 1 - reg
        elif reg:
            next_pc = target
        pc = next_pc
    halted = pc >= len(tokens)
    return " ".join(data) if halted else "", tuple(map(int, data)), reg, pc, halted


def observe(code, cap):
    io = ScriptedIO("unused")
    machine = _Machine(code, io)
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
    assert io.getvalue() == ""
    if machine.halted:
        machine.step()
        output = io.getvalue()
        snapshot = machine.snapshot()
        assert machine.rendered
        machine.step()
        machine.step()
        assert io.getvalue() == output
        assert machine.snapshot() == snapshot
    assert io.position() == 0
    assert vm_view(machine, "memory") == list(machine.deq)
    assert vm_view(machine, "stack") == [machine.reg]
    assert machine.ind == vm_view(machine, "ip")
    return (
        io.getvalue(),
        tuple(vm_view(machine, "memory")),
        machine.reg,
        vm_view(machine, "ip"),
        machine.halted,
    )


def corpus():
    commands = [
        "PUSH",
        "POP",
        "INJECT",
        "EJECT",
        "INVERT",
        "GOTO 0",
        "GOTO 2",
        "GOTO 7",
    ]
    yield from (
        " ".join(tokens)
        for n in range(4)
        for tokens in itertools.product(commands, repeat=n)
    )
    yield from [
        "INVERT INVERT INVERT PUSH",
        "INVERT GOTO 2 PUSH PUSH",
        "GOTO 2 PUSH PUSH",
        "INVERT GOTO 3 PUSH PUSH",
        "INVERT PUSH INVERT INJECT",
        "INVERT PUSH PUSH INVERT INJECT",
        "INVERT PUSH PUSH INVERT PUSH",
        "INVERT PUSH INVERT PUSH EJECT PUSH",
        "INVERT PUSH INVERT PUSH POP PUSH",
        "INVERT POP PUSH",
        "INVERT EJECT PUSH",
        "INVERT INVERT PUSH",
        "INVERTPUSH",
        "PUSHPOP",
        "GOTO12",
        "INVERT GOTO 2PUSH",
        "xPUSH",
        "x y PUSH",
        "PUSH x INVERT",
        "PUSH x y",
        "GOTO -1",
        "GOTO",
        "GOTO ²",
        "GOTO \u0660",
        "INVERT GOTO 999 PUSH",
        "INVERT GOTO 1",
    ]
    for separator in [" ", "  ", "\t", "\n", "\r\n", "\u2003"]:
        yield f"INVERT GOTO{separator}3 INVERT PUSH"
    rng = random.Random(1709)
    for _ in range(32):
        yield " ".join(rng.choices(commands, k=20))


@pytest.mark.parametrize("cap", [0, 1, 2, 9, 80])
def test_bounded_states_match_independent_string_deque(cap):
    for code in corpus():
        try:
            expected = reference(code, cap)
        except ValueError:
            with pytest.raises(ValueError, match="not a Bitdeque command"):
                observe(code, cap)
        else:
            assert observe(code, cap) == expected, (code, cap)


def test_run_matches_halting_reference():
    for code in corpus():
        try:
            expected = reference(code, 80)
        except ValueError:
            continue
        if expected[-1]:
            io = ScriptedIO("unused")
            run(code, io)
            assert io.getvalue() == expected[0], code
            assert io.position() == 0


@pytest.mark.parametrize(
    ("code", "output"),
    [
        ("PUSH PUSH PUSH", "0 0 0"),
        ("INVERT PUSH PUSH", "1 1"),
        ("PUSH POP PUSH", "0"),
        ("INVERT INVERT INVERT PUSH", "1"),
        ("POP", ""),
        ("INVERT GOTO 2 PUSH PUSH", "1 1"),
        ("GOTO 2 PUSH PUSH", "0 0"),
        ("INVERT GOTO 3 PUSH PUSH", "1"),
        ("INVERT PUSH INVERT INJECT", "0 1"),
        ("INVERT PUSH PUSH INVERT INJECT", "0 1 1"),
        ("INVERT PUSH PUSH INVERT PUSH", "1 1 0"),
        ("INVERT PUSH INVERT PUSH EJECT PUSH", "0 1"),
        ("INVERT PUSH INVERT PUSH POP PUSH", "1 0"),
        ("INVERT POP PUSH", "0"),
        ("INVERT EJECT PUSH", "0"),
        ("INVERT INVERT PUSH", "0"),
    ],
)
def test_reference_positive_controls(code, output):
    expected = reference(code, 80)
    assert expected[0] == output
    assert expected[-1]
    assert observe(code, 80) == expected


def test_snapshot_distinguishes_growth_at_equal_register_and_cursor():
    machine = _Machine("INVERT PUSH GOTO 1", ScriptedIO())
    machine.step()
    before = machine.snapshot()
    cursor = vm_view(machine, "ip"), machine.reg
    machine.step()
    machine.step()
    assert (vm_view(machine, "ip"), machine.reg) == cursor
    assert machine.deq == (1,)
    assert machine.snapshot() != before
    loop = reference("INVERT GOTO 1", 80)
    assert not loop[-1]
    assert loop[0] == ""
    assert observe("INVERT GOTO 1", 80) == loop


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table_in_independent_engine(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        template = esolangs.generate("Bitdeque", table)
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            code = esolangs.instantiate("Bitdeque", template, bits)
            result = reference(code, 10_000)
            assert result[-1], (table, row)
            assert result[0] == answer, (table, row)
            assert observe(code, 10_000) == result, (table, row)
            io = ScriptedIO("unused")
            run(code, io)
            assert io.getvalue() == answer
            assert io.position() == 0
