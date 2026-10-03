"""Independent list tape and byte strings, without production bitvector helpers."""

import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.minifuck import _Machine, run


def reference(code, stdin, cap):
    tape = [0] * 8
    ptr = pc = consumed = 0
    output = []
    error = None
    for _ in range(cap):
        if pc >= len(code):
            break
        command = code[pc]
        next_tape = tape.copy()
        next_ptr = ptr
        next_pc = pc + 1
        if command == "<":
            next_ptr = max(0, ptr - 1)
        elif command in ".[":
            next_ptr += 1
            while len(next_tape) <= next_ptr + 1:
                next_tape.append(0)
            next_tape[next_ptr] ^= 1
            if command == "[" and not next_tape[next_ptr]:
                next_tape[next_ptr + 1] ^= 1
                next_pc += 1
            elif command == ".":
                byte = int("".join(map(str, next_tape[:8])), 2)
                if byte:
                    output.append(chr(byte))
                elif consumed == len(stdin):
                    # A failed read commits none of this instruction's effects.
                    error = "EOFError"
                    break
                else:
                    next_tape[:8] = map(int, format(ord(stdin[consumed]) % 256, "08b"))
                    consumed += 1
        tape, ptr, pc = next_tape, next_ptr, next_pc
    return "".join(output), tuple(tape), ptr, pc, consumed, pc >= len(code), error


def observe(code, stdin, cap):
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    error = None
    try:
        for _ in range(cap):
            if machine.halted:
                break
            before = machine.ip
            machine.step()
            assert machine.ip > before
    except EOFError:
        error = "EOFError"
    assert machine.tape == machine.memory
    assert machine.ind == machine.ip
    assert machine.stack == []
    result = (
        io.getvalue(),
        tuple(machine.memory),
        machine.ptr,
        machine.ip,
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
        for length in range(6)
        for commands in itertools.product(".<[x", repeat=length)
    )
    yield from [
        "<[<.[<.",
        "abc",
        "[[[[[[[.",
        "X.",
        "X",
        "[[[[[[[<<<[<.",
        "[<[<<.",
        "[" * 8 + "<<." * 7 + "." * 6 + "[.",
        "[[[[[[[",
        ".<<[<<<.[<<.<<<..[<[.[.[..",
        "[.<",
        "[" * 64,
        "[" * 64 + "<" * 40 + "[<." * 20,
    ]
    rng = random.Random(1705)
    for _ in range(64):
        yield "".join(rng.choices(".<[x", k=30))


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


@pytest.mark.parametrize("stdin", ["", "ABCDEFGH", "\x00λ\xff\n😀"])
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 80])
def test_bounded_states_match_independent_byte_strings(stdin, cap):
    for code in corpus():
        assert observe(code, stdin, cap) == reference(code, stdin, cap), (
            code,
            stdin,
            cap,
        )


@pytest.mark.parametrize("stdin", ["", "ABCDEFGH", "\x00λ\xff\n😀"])
def test_run_matches_independent_engine(stdin):
    for code in corpus():
        expected = reference(code, stdin, len(code))
        assert expected[5] or expected[6]
        check_run(code, stdin, expected)


@pytest.mark.parametrize(
    ("code", "stdin", "output"),
    [
        ("<[<.[<.", "A", "A"),
        ("<[<.[<.", "B", "B"),
        ("abc", "A", ""),
        ("[[[[[[[.", "", "\x7f"),
        ("X.", "", "@"),
        ("X", "", ""),
        ("[[[[[[[<<<[<.", "", "{"),
        ("[<[<<.", "", "`"),
        ("[" * 8 + "<<." * 7 + "." * 6 + "[.", "A", "~|xp`@aqy}\x7f~"),
        (".<<[<<<.[<<.<<<..[<[.[.[..", "ABCDEFGH", "@`p0\x10"),
    ],
)
def test_reference_positive_controls(code, stdin, output):
    expected = reference(code, stdin, len(code))
    assert expected[0] == output
    assert expected[5:7] == (True, None)
    assert observe(code, stdin, len(code)) == expected
    check_run(code, stdin, expected)


def test_reference_controls_initial_growth_views_and_transactional_eof():
    assert reference("", "", 0) == ("", (0,) * 8, 0, 0, 0, True, None)
    growth = reference("[[[[[[[", "", 7)
    assert growth == ("", (0, 1, 1, 1, 1, 1, 1, 1, 0), 7, 7, 0, True, None)
    assert observe("[[[[[[[", "", 7) == growth
    views = reference("[.<", "", 3)
    assert views == ("`", (0, 1, 1, 0, 0, 0, 0, 0), 1, 3, 0, True, None)
    assert observe("[.<", "", 3) == views
    code = "<[<."
    before = reference(code, "", 3)
    failed = reference(code, "", 4)
    assert before[:6] == failed[:6]
    assert failed[6] == "EOFError"
    assert observe(code, "", 4) == failed


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table_in_independent_engine(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        template = esolangs.generate("Minifuck", table)
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            code = esolangs.instantiate("Minifuck", template, bits)
            stdin = ""
            result = reference(code, stdin, len(code))
            assert result[5:7] == (True, None), (table, row)
            assert result[0] == answer, (table, row)
            assert observe(code, stdin, len(code)) == result, (table, row)
            check_run(code, stdin, result)
