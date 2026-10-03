"""Independent literal parser and mutable registers; esolangs.org/wiki/Minsky_Swap."""

import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.register_based.minsky_swap import _Machine, run


def parse(code):
    commands = []
    targets = []
    readable = any(name + "(" in code for name in ("inc", "swap", "decnz"))
    if readable:
        for raw in code.splitlines():
            line = raw.strip()
            if not line:
                continue
            name, sep, rest = line.partition("(")
            if (
                not sep
                or name not in {"inc", "swap", "decnz"}
                or not rest.endswith(");")
            ):
                raise ValueError("invalid readable command")
            number = rest[:-2]
            if number and not number.isdecimal():
                raise ValueError("invalid readable operand")
            command = {"inc": "+", "swap": "*", "decnz": "~"}[name]
            commands.append(command)
            if command == "~":
                targets.append(int(number) if number else 1)
    else:
        lines = code.split("\n")
        commands = [char for char in lines[0] if char in "+*~"]
        if len(lines) > 1:
            digits = ""
            for char in lines[1] + " ":
                if char.isdecimal():
                    digits += char
                elif digits:
                    targets.append(int(digits))
                    digits = ""
    if commands.count("~") > len(targets):
        raise ValueError("missing jump target")
    operands = iter(targets)
    return [
        (command, next(operands) if command == "~" else None) for command in commands
    ]


def reference(code, cap):
    tokens = parse(code)
    registers = [0, 0]
    pc = focus = 0
    for _ in range(cap):
        if pc >= len(tokens):
            break
        command, target = tokens[pc]
        following = pc + 1
        if command == "+":
            registers[focus] += 1
        elif command == "*":
            focus = 1 - focus
        elif registers[focus] > 0:
            registers[focus] -= 1
        elif target != 0:
            following = target - 1
        pc = following
    halted = pc >= len(tokens)
    return (
        " ".join(map(str, registers)) if halted else "",
        tuple(registers),
        focus,
        pc,
        halted,
    )


def observe(code, cap):
    io = ScriptedIO("unused")
    machine = _Machine(code, io)
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
    assert io.getvalue() == ""
    assert io.position() == 0
    assert machine.stack == []
    assert machine.reg == tuple(machine.memory)
    assert machine.ind == machine.ip
    if machine.halted:
        machine.step()
        output = io.getvalue()
        snapshot = machine.snapshot()
        assert machine.dumped
        machine.step()
        machine.step()
        assert io.getvalue() == output
        assert machine.snapshot() == snapshot
    return io.getvalue(), tuple(machine.memory), machine.ptr, machine.ip, machine.halted


def readable(program, targets):
    jumps = iter(targets)
    return "\n".join(
        "inc();" if op == "+" else "swap();" if op == "*" else f"decnz({next(jumps)});"
        for op in program
    )


def corpus():
    for size in range(5):
        for chars in itertools.product("+*~", repeat=size):
            program = "".join(chars)
            for target in (0, 1, 2, 5):
                targets = [target] * program.count("~")
                yield program + "\n" + " ".join(map(str, targets))
                yield readable(program, targets)
    yield from [
        "+~\n1",
        "~+\n2",
        "~+~\n2 1",
        " ~++\n3",
        "decnz();",
        "~\n0",
        "++~+~\n2 1",
        "~+~+~\n3 2 1",
        "+++*+++*~+~\n2 1",
        "++*++*+++",
        "decnz(5);\ninc();\nswap();\ninc();\ninc();",
        "+" * 1000,
        "inc();swap();",
        "inc(); swap();",
        "inc(); +",
        "inc();\n+",
        "inc(1+2);\ninc();",
        "~~\n1",
        "x ~x++\n-3 garbage ٩\nignored ++",
        "inc(9);\nswap(2);\ninc();",
        "\n\tinc();\r\n\tdecnz(\u0661);\n",
    ]
    rng = random.Random(1712)
    for _ in range(32):
        program = "".join(rng.choices("+*~", k=20))
        targets = [rng.randrange(22) for _ in range(program.count("~"))]
        yield program + "\n" + " ".join(map(str, targets))
        yield readable(program, targets)


@pytest.mark.parametrize("cap", [0, 1, 2, 9, 1200])
def test_bounded_states_match_independent_mutable_registers(cap):
    for code in corpus():
        try:
            expected = reference(code, cap)
        except ValueError:
            with pytest.raises(ValueError, match=r"RMSN|unmatched"):
                observe(code, cap)
        else:
            assert observe(code, cap) == expected, (code, cap)


def test_run_matches_proven_halting_reference():
    for code in corpus():
        try:
            expected = reference(code, 1200)
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
        ("+", "1 0"),
        ("++", "2 0"),
        ("*+", "0 1"),
        ("+*+", "1 1"),
        ("+~\n1", "0 0"),
        ("~+\n2", "1 0"),
        ("~+~\n2 1", "0 0"),
        ("", "0 0"),
        ("  +  \n  ", "1 0"),
        (" ~++\n3", "1 0"),
        ("decnz(5);\ninc();\nswap();\ninc();\ninc();", "1 0"),
        ("+++~\n1", "2 0"),
        ("+*+*+", "2 1"),
        ("++~+~\n2 1", "1 0"),
        ("++*++*+++", "5 2"),
        ("~\n999", "0 0"),
        ("~+~+~\n3 2 1", "0 0"),
        ("+++*+++", "3 3"),
        ("+++*+++*~+~\n2 1", "2 3"),
        ("inc();\nswap();\ninc();\ninc();\nswap();\ndecnz(1);", "0 2"),
        ("+" * 1000, "1000 0"),
        ("~\n0", "0 0"),
    ],
)
def test_reference_positive_controls(code, output):
    expected = reference(code, 1200)
    assert expected[0] == output
    assert expected[-1]
    assert observe(code, 1200) == expected


def test_cycle_and_growth_controls_distinguish_registers_at_equal_cursor():
    assert reference("decnz();", 80) == ("", (0, 0), 0, 0, False)
    assert observe("decnz();", 80) == reference("decnz();", 80)
    machine = _Machine("*+*~\n1", ScriptedIO())
    before = machine.snapshot()
    for _ in range(4):
        machine.step()
    assert machine.ip == machine.ptr == 0
    assert machine.reg == (0, 1)
    assert machine.snapshot() != before
    assert observe("*+*~\n1", 80) == ("", (0, 20), 0, 0, False)


def test_snapshot_distinguishes_pointer_at_equal_cursor_and_registers():
    machine = _Machine("*~\n1", ScriptedIO())
    before = machine.snapshot()
    machine.step()
    machine.step()
    assert machine.ip == 0
    assert machine.reg == (0, 0)
    assert machine.ptr == 1
    assert machine.snapshot() != before
    assert observe("*~\n1", 2) == reference("*~\n1", 2)


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.parametrize("width", [None, 9, 12, 16])
def test_every_small_generated_table_in_independent_engine(n, width):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        template = esolangs.generate("Minsky Swap", table, width=width)
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            code = esolangs.instantiate("Minsky Swap", template, bits)
            result = reference(code, 10_000)
            assert result[-1], (table, row, width)
            assert result[1][1] == int(answer), (table, row, width)
            assert observe(code, 10_000) == result, (table, row, width)
            io = ScriptedIO("unused")
            run(code, io)
            assert io.getvalue() == result[0]
            assert io.position() == 0
