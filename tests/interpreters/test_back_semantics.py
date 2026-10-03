"""Independent complex beam and mutable tape; esolangs.org/wiki/Back."""

import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.back import _Machine, run


def reference(code, cap):
    if not code or all(not line.strip() for line in code):
        raise ValueError("empty grid")
    width = max(map(len, code))
    cells = {
        complex(x, y): char
        for y, line in enumerate(code)
        for x, char in enumerate(line)
    }
    point = 0j
    direction = 1 + 0j
    tape = [0]
    pointer = 0
    stopped = False
    for _ in range(cap):
        command = cells.get(point, " ")
        distance = 1
        if command == "*":
            stopped = True
            break
        if command == "\\":
            direction = 1j * direction.conjugate()
        elif command == "/":
            direction = -1j * direction.conjugate()
        elif command == "<":
            pointer = max(0, pointer - 1)
        elif command == ">":
            pointer += 1
            if pointer >= len(tape):
                tape.append(0)
        elif command == "-":
            tape[pointer] = 1 - tape[pointer]
        elif command == "+" and tape[pointer] == 0:
            distance = 2
        point += distance * direction
        point = complex(point.real % width, point.imag % len(code))
    return (
        " ".join(map(str, tape)) if stopped else "",
        tuple(tape),
        pointer,
        (int(point.imag), int(point.real), int(direction.imag), int(direction.real)),
        stopped,
    )


def observe(code, cap):
    io = ScriptedIO("unused")
    machine = _Machine(code, io)
    assert isinstance(machine.halted, bool)
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
    assert io.getvalue() == ""
    assert machine.stack == []
    assert machine.tape == tuple(machine.memory)
    assert machine.cell == machine.ptr
    assert machine.ip == (machine.row, machine.col, machine.a, machine.b)
    assert io.position() == machine.input_position() == 0
    if machine.halted:
        machine.step()
        output = io.getvalue()
        before = machine.snapshot()
        assert machine.dumped
        machine.step()
        machine.step()
        assert machine.snapshot() == before
        assert io.getvalue() == output
    return io.getvalue(), tuple(machine.memory), machine.ptr, machine.ip, machine.halted


def corpus():
    for n in range(1, 4):
        for cells in itertools.product("\\/<>-+*.", repeat=n):
            yield ["".join(cells)]
    for cells in itertools.product("\\/<>-+*.", repeat=4):
        yield ["".join(cells[:2]), "".join(cells[2:])]
    yield from [
        [],
        [""],
        ["   ", "\t"],
        ["\\\\", " *"],
        ["//", " *"],
        [">--*"],
        [">+-*"],
        [">>-<*"],
        [">-<-*"],
        ["\\", "-", "*"],
        ["/*", "--"],
        ["\\", "+", "-", "*"],
        ["\\", "\\-*"],
        ["><>*"],
        [">>*"],
        ["<-*"],
        ["λ", " *"],
        ["", "-*"],
        [">"],
        ["-"],
    ]
    rng = random.Random(1713)
    for _ in range(32):
        yield [
            "".join(rng.choices("\\/<>-+*. λ", k=rng.randrange(7)))
            for _ in range(rng.randrange(5))
        ]


@pytest.mark.parametrize("cap", [0, 1, 2, 9, 80])
def test_bounded_states_match_independent_complex_beam(cap):
    for code in corpus():
        try:
            expected = reference(code, cap)
        except ValueError:
            with pytest.raises(ValueError, match="Back program cannot be empty"):
                observe(code, cap)
        else:
            assert observe(code, cap) == expected, (code, cap)


def test_run_matches_proven_halting_reference():
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
        (["*"], "0"),
        (["-*"], "1"),
        ([">-*"], "0 1"),
        ([">--*"], "0 0"),
        ([">+-*"], "0 0"),
        (["\\-*"], "1"),
        (["/-*"], "1"),
        ([">>-<*"], "0 0 1"),
        ([">-<-*"], "1 1"),
        (["\\", "-", "*"], "1"),
        (["/*", "--"], "1"),
        (["\\", "+", "-", "*"], "0"),
        (["\\", "\\-*"], "1"),
        (["<-*"], "1"),
        (["><>*"], "0 0"),
        ([">>*"], "0 0 0"),
        (["\\\\", " *"], "0"),
        (["//", " *"], "0"),
    ],
)
def test_reference_positive_controls(code, output):
    expected = reference(code, 80)
    assert expected[0] == output
    assert expected[-1]
    assert observe(code, 80) == expected
    io = ScriptedIO("unused")
    run(code, io)
    assert io.getvalue() == output


def test_snapshot_distinguishes_growing_and_flipped_tape_at_equal_beam_position():
    for code in ([">"], ["-"]):
        machine = _Machine(code, ScriptedIO())
        before = machine.snapshot()
        beam = machine.ip
        machine.step()
        assert machine.ip == beam
        assert machine.snapshot() != before
    assert observe([">"], 80) == ("", (0,) * 81, 80, (0, 0, 0, 1), False)
    assert observe(["-"], 80) == ("", (0,), 0, (0, 0, 0, 1), False)


def test_snapshot_distinguishes_direction_and_pointer_with_other_fields_equal():
    mirror = _Machine(["\\"], ScriptedIO())
    before = mirror.snapshot()
    mirror.step()
    assert mirror.row == mirror.col == mirror.ptr == 0
    assert mirror.tape == (0,)
    assert (mirror.a, mirror.b) == (1, 0)
    assert mirror.snapshot() != before
    pointer = _Machine(["<"], ScriptedIO())
    pointer.state = (0, 0, 0, 1, (0, 0), 1, False)
    before = pointer.snapshot()
    pointer.step()
    assert pointer.ip == (0, 0, 0, 1)
    assert pointer.tape == (0, 0)
    assert pointer.ptr == 0
    assert pointer.snapshot() != before


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table_in_independent_engine(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        template = esolangs.generate("Back", table)
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            code = esolangs.instantiate("Back", template, bits).split("\n")
            result = reference(code, 10_000)
            assert result[-1], (table, row)
            assert result[1][n] == int(answer), (table, row)
            assert observe(code, 10_000) == result, (table, row)
            io = ScriptedIO("unused")
            run(code, io)
            assert io.getvalue() == result[0]
            assert io.position() == 0
