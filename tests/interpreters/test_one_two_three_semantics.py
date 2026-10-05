"""Independent signed-location bit tape and inline jump searches."""

import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.one_two_three import _Machine, run
from tests.interpreters.views import view as vm_view


def reference(code, stdin, cap, initial=None, *, detect_cycle=False):
    pc, pos, locations = initial if initial is not None else (0, 0, ())
    tape = dict.fromkeys(locations, 1)
    consumed = 0
    output = []
    halted = not code
    error = None
    seen = {}
    cycle_start = None
    steps = 0
    for _ in range(cap):
        if halted:
            break
        if detect_cycle:
            key = pc, pos, tuple(sorted(tape)), consumed
            if key in seen:
                cycle_start = seen[key]
                break
            seen[key] = steps
        steps += 1
        if pc >= len(code):
            if pos < 0:
                halted = True
            else:
                pc = 0
            continue
        command = code[pc]
        if command == "1":
            if pos in tape:
                del tape[pos]
            else:
                tape[pos] = 1
            pos -= 1
            if pos == -4:
                pos = 0
        elif command == "2":
            if pos == -3:
                if consumed == len(stdin):
                    error = "EOFError"
                    break
                byte = ord(stdin[consumed])
                consumed += 1
                for bit in range(8):
                    tape.pop(bit, None)
                    if (byte // (2**bit)) % 2:
                        tape[bit] = 1
                pos = 0
            elif pos == -2:
                byte = sum(2**bit for bit in range(8) if bit in tape)
                output.append(chr(byte))
                pos = 0
            else:
                pos += 1
        elif command == "3" and pos >= 0:
            direction = -1 if pos in tape else 1
            target = pc + direction
            while 0 <= target < len(code) and code[target] != "3":
                target += direction
            pc = target + 1
            continue
        pc += 1
    result = "".join(output), tuple(sorted(tape)), pos, pc, consumed, halted, error
    return (result, cycle_start, steps) if detect_cycle else result


def observe(code, stdin, cap, initial=None):
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    if initial is not None:
        machine.place(initial[0], initial[1], frozenset(initial[2]))
    error = None
    try:
        for _ in range(cap):
            if machine.halted:
                break
            machine.step()
    except EOFError:
        error = "EOFError"
    byte = sum(2**bit for bit in range(8) if bit in machine.bits)
    assert machine.byte() == byte
    assert vm_view(machine, "memory") == [byte]
    assert vm_view(machine, "stack") == []
    result = (
        io.getvalue(),
        tuple(sorted(machine.bits)),
        machine.pos,
        vm_view(machine, "ip"),
        io.position(),
        machine.halted,
        error,
    )
    if machine.halted:
        snapshot = machine.snapshot()
        machine.step()
        machine.step()
        assert machine.snapshot() == snapshot
        assert io.getvalue() == result[0]
    return result


def corpus():
    yield from (
        "".join(commands)
        for length in range(5)
        for commands in itertools.product("123x", repeat=length)
    )
    yield from [
        " \n abc \n",
        "212222222112112112112112112112112\n1",
        "hello 212222222112112112112112112112112\n1",
        "111212112",
        "3231",
        "331",
        "132231",
        "1121",
        "2131",
        "33112",
        "2" * 9 + "1",
        "2" * 9 + "1" * 16 + "2",
    ]
    rng = random.Random(1706)
    for _ in range(64):
        yield "".join(rng.choices("123x", k=20))


def check_run(code, stdin, expected):
    io = ScriptedIO(stdin)
    error = None
    try:
        run(code, io)
    except EOFError:
        error = "EOFError"
    assert (io.getvalue(), io.position(), error) == (
        expected[0],
        expected[4],
        expected[6],
    ), (code, stdin)


@pytest.mark.parametrize("stdin", ["", "h\ni", "\x00\x81λ😀"])
@pytest.mark.parametrize("cap", [0, 1, 2, 8, 80])
def test_bounded_states_match_independent_signed_tape(stdin, cap):
    for code in corpus():
        assert observe(code, stdin, cap) == reference(code, stdin, cap), (
            code,
            stdin,
            cap,
        )


@pytest.mark.parametrize("stdin", ["", "h\ni", "\x00\x81λ😀"])
def test_run_matches_halting_or_eof_reference(stdin):
    for code in corpus():
        expected = reference(code, stdin, 80)
        if expected[5] or expected[6]:
            check_run(code, stdin, expected)


@pytest.mark.parametrize(
    ("code", "cap", "output", "halted"),
    [
        ("", 0, "", True),
        (" \n abc \n", 80, "", False),
        ("212222222112112112112112112112112\n1", 80, "\x82", True),
        ("hello 212222222112112112112112112112112\n1", 80, "\x82", True),
        ("3231", 80, "", True),
        ("331", 80, "", True),
        ("132231", 80, "", True),
        ("1121", 80, "\x01", True),
        ("2131", 80, "", False),
        ("33112", 20, "\x01", False),
    ],
)
def test_reference_positive_controls(code, cap, output, halted):
    expected = reference(code, "", cap)
    assert (expected[0], expected[5], expected[6]) == (output, halted, None)
    assert observe(code, "", cap) == expected


def test_reads_preserve_outside_bits_and_failed_reads_preserve_state():
    initial = (0, -3, (-2, 8, 100))
    expected = reference("2", "\x81", 1, initial)
    assert expected == ("", (-2, 0, 7, 8, 100), 0, 1, 1, False, None)
    assert observe("2", "\x81", 1, initial) == expected
    failed = reference("2", "", 1, initial)
    assert failed == ("", (-2, 8, 100), -3, 0, 0, False, "EOFError")
    assert observe("2", "", 1, initial) == failed
    grown = reference("2" * 9 + "1", "", 10)
    assert grown == ("", (9,), 8, 10, 0, False, None)
    assert observe("2" * 9 + "1", "", 10) == grown


@pytest.mark.parametrize("code", ["3", "3xx3", "33", "x3x3x3"])
@pytest.mark.parametrize("pos", [-3, -2, -1, 0, 2, 9])
@pytest.mark.parametrize("on", [False, True])
def test_placed_jump_states_use_the_nearest_marker(code, pos, on):
    for pc, command in enumerate(code):
        if command == "3":
            initial = (pc, pos, (pos,) if on else ())
            assert observe(code, "", 1, initial) == reference(code, "", 1, initial)


def test_cycle_certificate_distinguishes_growth_from_a_repeated_state():
    halting, start, _ = reference("1", "", 80, detect_cycle=True)
    assert halting[5]
    assert start is None
    loop, start, steps = reference("x", "", 80, detect_cycle=True)
    assert not loop[5]
    assert start == 0
    assert steps == 2
    growing, start, _ = reference("2", "", 80, detect_cycle=True)
    assert not growing[5]
    assert start is None


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table_in_independent_engine(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        program = esolangs.generate("123", table)
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            if esolangs.describe("123")["parameterized"]:
                code = esolangs.instantiate("123", program, bits)
                stdin = ""
            else:
                code = program
                stdin = esolangs.encode_inputs("123", bits, table)
            result, cycle_start, steps = reference(
                code, stdin, 100_000, detect_cycle=True
            )
            assert result[6] is None, (table, row)
            assert result[5] or cycle_start is not None, (table, row)
            assert str(int(cycle_start is not None)) == answer, (table, row)
            assert observe(code, stdin, steps) == result, (table, row)
            if cycle_start is None:
                check_run(code, stdin, result)
            else:
                first = observe(code, stdin, cycle_start)
                assert first[1:6] == result[1:6], (table, row)
