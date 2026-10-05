"""Independent character lexer, mutable tape and ordinal marker scans."""

import itertools
import random

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.six_five import _Machine, run
from tests.interpreters.views import view as vm_view


def lex(code):
    tokens = []
    stream = iter(code)
    for char in stream:
        if char == "C":
            for comment in stream:
                if comment == "\n":
                    tokens.append(comment)
                    break
        elif char in "78":
            tokens.append(char + next(stream, ""))
        else:
            tokens.append(char)
    return tokens


def operand(token):
    if len(token) == 1:
        return 0
    char = token[1].upper()
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return digits.index(char) if char in digits else int(char)


def reference(code, stdin, cap):
    tokens = lex(code)
    tape = [0]
    pc = ptr = consumed = 0
    output = []
    error = None
    for _ in range(cap):
        if pc >= len(tokens):
            break
        token = tokens[pc]
        next_pc = pc + 1
        if token == "1":
            ptr += 2
            while len(tape) <= ptr:
                tape.append(0)
        elif token == "3":
            ptr = max(0, ptr - 1)
        elif token in ("5", "6", "2", "9"):
            tape[ptr] += {"5": 5, "6": 6, "2": -5, "9": -6}[token]
        elif token.startswith("7"):
            if tape[ptr] == operand(token):
                next_pc += 1
        elif token.startswith("8"):
            wanted = operand(token)
            ordinal = 0
            for at, candidate in enumerate(tokens):
                if candidate == "4":
                    ordinal += 1
                    if ordinal == wanted:
                        next_pc = at + 1
                        break
        elif token == "0":
            next_pc = len(tokens)
        elif token == "A":
            if not 0 <= tape[ptr] <= 0x10FFFF:
                error = "HaltError"
                break
            output.append(chr(tape[ptr]))
        elif token == "B":
            if consumed == len(stdin):
                error = "EOFError"
                break
            tape[ptr] = ord(stdin[consumed])
            consumed += 1
        pc = next_pc
    return "".join(output), tuple(tape), ptr, pc, consumed, pc >= len(tokens), error


def observe(code, stdin, cap):
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    assert machine.toks == lex(code)
    error = None
    try:
        for _ in range(cap):
            if machine.halted:
                break
            machine.step()
    except EOFError:
        error = "EOFError"
    except HaltError:
        error = "HaltError"
    assert machine.ind == vm_view(machine, "ip")
    assert machine.cell == machine.ptr
    assert vm_view(machine, "memory") == list(machine.tape)
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
        for commands in itertools.product(
            ["0", "1", "2", "3", "4", "5", "6", "9", "A", "B", "70", "81"],
            repeat=length,
        )
    )
    yield from [
        "66666666A0",
        "5555555A0",
        "BA0",
        "15555555555A0",
        "313A0",
        "70A0",
        "6666666671A0",
        "8166666666A0",
        "166666666A366666666A0",
        "11",
        "066666666A0",
        "5A5A0",
        "B5A0",
        "81A4A0",
        "825A46A4A0",
        "55A7A5A0",
        "2A",
        "B62A",
        "1366666666113A0",
        "4A8",
        "A7",
        "6C66666666A0",
        "66666666A0C66666666A0",
        "6C hidden\n66666666A0",
        "C66666666A0\n66666666A0",
        "667C66666666A0",
        "7C",
        "78",
        "7",
        "8",
        "7C1",
        "6C hidden",
        "X6",
        "X66666666A0",
        "78C1",
        "7F",
        "8Z",
        "4A82A40",
        "481",
        "4C hide\n81",
        "BBA",
        "11331",
    ]
    rng = random.Random(1707)
    pieces = [
        "1",
        "3",
        "5",
        "6",
        "2",
        "9",
        "A",
        "B",
        "70",
        "75",
        "7C",
        "4",
        "81",
        "82",
        "8Z",
        "x",
    ]
    for _ in range(64):
        yield "".join(rng.choices(pieces, k=20))


def check_run(code, stdin, expected):
    io = ScriptedIO(stdin)
    error = None
    try:
        run(code, io)
    except EOFError:
        error = "EOFError"
    except HaltError:
        error = "HaltError"
    assert (io.getvalue(), io.position(), error) == (
        expected[0],
        expected[4],
        expected[6],
    ), (code, stdin)


@pytest.mark.parametrize("stdin", ["", "XY\n", "\x00λ\U0010ffff"])
@pytest.mark.parametrize("cap", [0, 1, 2, 8, 80])
def test_bounded_states_match_independent_lexer_and_scans(stdin, cap):
    for code in corpus():
        assert observe(code, stdin, cap) == reference(code, stdin, cap), (
            code,
            stdin,
            cap,
        )


@pytest.mark.parametrize("stdin", ["", "XY\n", "\x00λ\U0010ffff"])
def test_run_matches_halting_or_error_reference(stdin):
    for code in corpus():
        expected = reference(code, stdin, 80)
        if expected[5] or expected[6]:
            check_run(code, stdin, expected)


@pytest.mark.parametrize(
    ("code", "stdin", "output"),
    [
        ("66666666A0", "", "0"),
        ("5555555A0", "", "#"),
        ("BA0", "X", "X"),
        ("0", "", ""),
        ("15555555555A0", "", "2"),
        ("313A0", "", "\x00"),
        ("70A0", "", ""),
        ("6666666671A0", "", "0"),
        ("8166666666A0", "", "0"),
        ("166666666A366666666A0", "", "00"),
        ("066666666A0", "", ""),
        ("5A5A0", "", "\x05\n"),
        ("B5A0", "A", "F"),
        ("81A4A0", "", "\x00"),
        ("825A46A4A0", "", "\x00"),
        ("55A7A5A0", "", "\n\n"),
        ("1366666666113A0", "", "\x00"),
        ("4A8", "", "\x00"),
        ("A7", "", "\x00"),
        ("6C66666666A0", "", ""),
        ("66666666A0C66666666A0", "", "0"),
        ("6C hidden\n66666666A0", "", "6"),
        ("667C66666666A0", "", "6"),
        ("X66666666A0", "", "0"),
        ("BA0", "\U0010ffff", "\U0010ffff"),
    ],
)
def test_reference_positive_controls(code, stdin, output):
    expected = reference(code, stdin, 80)
    assert (expected[0], expected[5], expected[6]) == (output, True, None)
    assert observe(code, stdin, 80) == expected
    check_run(code, stdin, expected)


def test_reference_controls_errors_loop_boundaries_and_operandless_skip():
    assert reference("7", "", 1) == ("", (0,), 0, 2, 0, True, None)
    assert reference("81A4A0", "", 1)[3] == 3
    assert reference("11", "", 2) == ("", (0, 0, 0, 0, 0), 4, 2, 0, True, None)
    for code, stdin, kind in [
        ("2A", "", "HaltError"),
        ("B62A", "\U0010ffff", "HaltError"),
        ("B", "", "EOFError"),
    ]:
        result = reference(code, stdin, 80)
        assert result[6] == kind
        assert not result[5]
        assert observe(code, stdin, 80) == result
    loop = reference("481", "", 80)
    assert loop[5:7] == (False, None)
    assert observe("481", "", 80) == loop


@pytest.mark.parametrize("prefix", ["77", "78", "87", "88"])
def test_operand_seven_or_eight_does_not_protect_following_comment(prefix):
    code = prefix + "C66666666A0"
    assert lex(code) == [prefix]
    expected = reference(code, "", 80)
    assert expected == ("", (0,), 0, 1, 0, True, None)
    assert observe(code, "", 80) == expected
    check_run(code, "", expected)
    continued = code + "\n66666666A0"
    expected = reference(continued, "", 80)
    assert expected[0] == "0"
    assert observe(continued, "", 80) == expected
    check_run(continued, "", expected)


@pytest.mark.parametrize(
    ("code", "tokens"),
    [
        ("7C", ["7C"]),
        ("78", ["78"]),
        ("7", ["7"]),
        ("8", ["8"]),
        ("7C1", ["7C", "1"]),
        ("6C hidden", ["6"]),
        ("X6", ["X", "6"]),
    ],
)
def test_reference_lexer_controls_operand_boundaries(code, tokens):
    assert lex(code) == tokens
    assert _Machine(code, ScriptedIO()).toks == tokens


def test_snapshot_distinguishes_equal_cursors_with_different_data_or_input():
    machine = _Machine("4581", ScriptedIO())
    machine.step()
    before = machine.snapshot()
    cursor = vm_view(machine, "ip"), machine.ptr
    machine.step()
    machine.step()
    assert (vm_view(machine, "ip"), machine.ptr) == cursor
    assert vm_view(machine, "memory") == [5]
    assert machine.snapshot() != before
    io = ScriptedIO("AA")
    reader = _Machine("4B81", io)
    for _ in range(3):
        reader.step()
    before = reader.snapshot()
    cursor = reader.ip, reader.ptr
    memory = reader.memory
    reader.step()
    reader.step()
    assert (reader.ip, reader.ptr) == cursor
    assert reader.memory == memory
    assert io.position() == 2
    assert reader.snapshot() != before


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table_in_independent_engine(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        code = esolangs.generate("6-5", table)
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            stdin = esolangs.encode_inputs("6-5", bits, table)
            result = reference(code, stdin, 10_000)
            assert result[5:7] == (True, None), (table, row)
            assert result[0] == answer, (table, row)
            assert observe(code, stdin, 10_000) == result, (table, row)
            check_run(code, stdin, result)
