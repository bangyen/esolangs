"""Independent fixed tape with inline bidirectional loop scans."""

import itertools

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.smallfuck import _Machine, run
from tests.interpreters.views import view as vm_view


def reference(code, cap):
    depth = 0
    for command in code:
        depth += (command == "[") - (command == "]")
        if depth < 0:
            raise ValueError("unmatched close")
    if depth:
        raise ValueError("unmatched open")
    tape = [0] * len(code)
    ptr = pc = 0
    for _ in range(cap):
        if pc == len(code):
            break
        command = code[pc]
        if command == "*":
            tape[ptr] ^= 1
        elif command == ">":
            ptr += 1
            if ptr == len(tape):
                pc = len(code)
                break
        elif command == "<":
            if ptr == 0:
                pc = len(code)
                break
            ptr -= 1
        elif command == "[" and not tape[ptr]:
            depth = 1
            while depth:
                pc += 1
                depth += (code[pc] == "[") - (code[pc] == "]")
        elif command == "]" and tape[ptr]:
            depth = 1
            while depth:
                pc -= 1
                depth += (code[pc] == "]") - (code[pc] == "[")
        pc += 1
    halted = pc == len(code)
    output = str(tape[2] if len(tape) > 2 else 0) if halted else ""
    return output, tuple(tape), ptr, pc, halted


def observe(code, cap):
    io = ScriptedIO("unused")
    machine = _Machine(code, io)
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
    if machine.halted:
        machine.step()
        output = io.getvalue()
        snapshot = machine.snapshot()
        machine.step()
        assert io.getvalue() == output
        assert machine.snapshot() == snapshot
    assert io.position() == 0
    assert vm_view(machine, "stack") == []
    assert tuple(vm_view(machine, "memory")) == machine.tape
    return (
        io.getvalue(),
        tuple(vm_view(machine, "memory")),
        machine.ptr,
        vm_view(machine, "ip"),
        machine.halted,
    )


def corpus():
    yield from (
        "".join(commands)
        for length in range(5)
        for commands in itertools.product("*<>[]x", repeat=length)
    )
    yield from ["*>*[*]", ">>*", "*[>*[**]<*]", "[*[[]]]", "*[[]]", "<*"]


@pytest.mark.parametrize("cap", [0, 1, 2, 9, 80])
def test_bounded_execution_matches_independent_scans(cap):
    for code in corpus():
        try:
            expected = reference(code, cap)
        except ValueError:
            with pytest.raises(ValueError, match="unmatched"):
                observe(code, cap)
        else:
            assert observe(code, cap) == expected, (code, cap)


def test_run_matches_halting_reference_cases():
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
    ("code", "expected"),
    [
        ("", ("0", (), 0, 0, True)),
        ("<*", ("0", (0, 0), 0, 2, True)),
        (">>", ("0", (0, 0), 2, 2, True)),
        ("*x", ("0", (1, 0), 0, 2, True)),
        (">>*", ("1", (0, 0, 1), 2, 3, True)),
        ("*>*[*]", ("0", (1, 0, 0, 0, 0, 0), 1, 6, True)),
        ("*[]", ("", (1, 0, 0), 0, 2, False)),
    ],
)
def test_reference_positive_controls(code, expected):
    assert reference(code, 80) == expected
    assert observe(code, 80) == expected


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table_in_independent_engine(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        template = esolangs.generate("Smallfuck", table)
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            code = esolangs.instantiate("Smallfuck", template, bits)
            result = reference(code, 10_000)
            assert result[-1], (table, row)
            assert result[0] == answer, (table, row)
            assert observe(code, 10_000) == result, (table, row)
