"""Independent mutable tape and inline bracket scans for both execution paths."""

import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.brainfuck import _Machine, run
from tests.interpreters.views import view as vm_view


def reference(code, stdin, cap):
    depth = 0
    for char in code:
        depth += (char == "[") - (char == "]")
        if depth < 0:
            raise ValueError("unmatched close")
    if depth:
        raise ValueError("unmatched open")
    tape = [0]
    pc = ptr = consumed = 0
    output = []
    error = None
    for _ in range(cap):
        if pc == len(code):
            break
        char = code[pc]
        if char == "+":
            tape[ptr] = (tape[ptr] + 1) % 256
        elif char == "-":
            tape[ptr] = (tape[ptr] - 1) % 256
        elif char == ">":
            ptr += 1
            if ptr == len(tape):
                tape.append(0)
        elif char == "<":
            ptr = max(0, ptr - 1)
        elif char == ".":
            output.append(chr(tape[ptr]))
        elif char == ",":
            if consumed == len(stdin):
                error = "EOFError"
                break
            tape[ptr] = ord(stdin[consumed]) % 256
            consumed += 1
        elif char == "[" and not tape[ptr]:
            depth = 1
            while depth:
                pc += 1
                depth += (code[pc] == "[") - (code[pc] == "]")
        elif char == "]" and tape[ptr]:
            depth = 1
            while depth:
                pc -= 1
                depth += (code[pc] == "]") - (code[pc] == "[")
        pc += 1
    return "".join(output), tuple(tape), ptr, pc, consumed, pc == len(code), error


def observe(code, stdin, cap):
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    error = None
    try:
        for _ in range(cap):
            if machine.halted:
                break
            machine.step()
    except EOFError:
        error = "EOFError"
    assert vm_view(machine, "memory") == list(machine.tape)
    assert machine.ind == vm_view(machine, "ip")
    assert machine.input_position() == io.position()
    assert vm_view(machine, "stack") == []
    result = (
        io.getvalue(),
        tuple(vm_view(machine, "memory")),
        machine.ptr,
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
        for length in range(4)
        for commands in itertools.product("+-<>.,x", repeat=length)
    )
    yield from [
        "+" * 65 + ".",
        "+" * 256 + ".",
        "-.",
        "abc+++abc.abc",
        "++>++<.>.>",
        "<<.",
        ",>,<.>.",
        ">+>++",
        "+[-].",
        "[.]",
        "++[>+<-]>.>.",
        "+++[>++[>+<-]<-]>+++.",
        "+[]",
        "[[]]",
        "++[+].",
        "+++>++++<[>++<-]>. ",
        "[>++++<-]>. ",
        "-[>+<-]>. ",
        ",+.",
        ",[.,]",
        "+<.",
        "+[>--<-]>.",
        "+[>+-<-]>.",
        "+[>++++<-]>[<+>-]<.",
        "[",
        "]",
        "+]",
    ]
    rng = random.Random(0)
    for _ in range(100):
        yield "".join(rng.choice("+-<>.abc") for _ in range(200))


@pytest.mark.parametrize("stdin", ["", "AB", "Āā😀\n\xff"])
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 80, 1000])
def test_bounded_execution_matches_independent_tape(stdin, cap):
    for code in corpus():
        try:
            expected = reference(code, stdin, cap)
        except ValueError:
            with pytest.raises(ValueError, match="unmatched"):
                observe(code, stdin, cap)
        else:
            assert observe(code, stdin, cap) == expected, (code, stdin, cap)


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


@pytest.mark.parametrize("stdin", ["", "AB", "Āā😀\n\xff"])
def test_fast_run_matches_halting_or_error_reference(stdin):
    for code in corpus():
        try:
            expected = reference(code, stdin, 5000)
        except ValueError:
            with pytest.raises(ValueError, match="unmatched"):
                run(code, ScriptedIO(stdin))
        else:
            if expected[5] or expected[6]:
                check_run(code, stdin, expected)


@pytest.mark.parametrize(
    ("code", "stdin", "output", "tape", "ptr"),
    [
        ("+" * 65 + ".", "", "A", (65,), 0),
        ("+" * 256 + ".", "", "\x00", (0,), 0),
        ("-.", "", "\xff", (255,), 0),
        ("abc+++abc.abc", "", "\x03", (3,), 0),
        ("++>++<.>.>", "", "\x02\x02", (2, 2, 0), 2),
        ("<<.", "", "\x00", (0,), 0),
        (",>,<.>.", "AB", "AB", (65, 66), 1),
        ("+[-].", "", "\x00", (0,), 0),
        ("[.]", "", "", (0,), 0),
        ("++[>+<-]>.>.", "", "\x02\x00", (0, 2, 0), 2),
        ("+++[>++[>+<-]<-]>+++.", "", "\x03", (0, 3, 6), 1),
        (">+>++", "", "", (0, 1, 2), 2),
        (",.", "😀", "\x00", (0,), 0),
    ],
)
def test_reference_positive_controls(code, stdin, output, tape, ptr):
    expected = reference(code, stdin, 5000)
    assert expected[:3] == (output, tape, ptr)
    assert expected[5:7] == (True, None)
    assert observe(code, stdin, 5000) == expected
    check_run(code, stdin, expected)


def test_eof_preserves_pre_read_state_and_step_cap_is_not_halt():
    expected = reference(">+,", "", 10)
    assert expected == ("", (0, 1), 1, 2, 0, False, "EOFError")
    assert observe(">+,", "", 10) == expected
    loop = reference("+[]", "", 80)
    assert not loop[5]
    assert loop[6] is None
    assert observe("+[]", "", 80) == loop


def test_equal_cells_at_different_input_positions_have_different_snapshots():
    machine = _Machine(",[,]", ScriptedIO("AA"))
    machine.step()
    machine.step()
    before = machine.snapshot()
    memory = vm_view(machine, "memory")
    position = vm_view(machine, "ip")
    machine.step()
    machine.step()
    assert vm_view(machine, "ip") == position
    assert vm_view(machine, "memory") == memory
    assert machine.snapshot() != before


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table_in_independent_engine(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        code = esolangs.generate("brainfuck", table)
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            stdin = esolangs.encode_inputs("brainfuck", bits, table)
            result = reference(code, stdin, 25_000)
            assert result[5:7] == (True, None), (table, row)
            assert result[0] == answer, (table, row)
            assert observe(code, stdin, 25_000) == result, (table, row)
            check_run(code, stdin, result)
