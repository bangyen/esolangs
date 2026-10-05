"""Independent Unary decoding (Unary revision 192570) over the Brainfuck oracle.

The wiki's length -> binary -> 3-bit table is modelled here; execution reuses
the independent Brainfuck reference.  Empty source and whitespace are not
covered by the wiki (its own example only adds line breaks "for
readability"); the model pins the shipped choices: whitespace is ignored,
zero digits decode to empty Brainfuck, other symbols are refused.
"""

import itertools

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.unary import _Machine, run
from tests.interpreters.test_brainfuck_semantics import reference as brainfuck
from tests.interpreters.views import view as vm_view

TABLE = {
    "000": ">",
    "001": "<",
    "010": "+",
    "011": "-",
    "100": ".",
    "101": ",",
    "110": "[",
    "111": "]",
}


def decode(code):
    if any(char not in "0" and not char.isspace() for char in code):
        raise ValueError("Unary: not zeros")
    zeros = code.count("0")
    if zeros == 0:
        return ""
    bits = format(zeros, "b")
    if (len(bits) - 1) % 3:
        raise ValueError("Unary: no leading 1 before whole triples")
    return "".join(TABLE[bits[i : i + 3]] for i in range(1, len(bits), 3))


def encode(commands):
    bits = "1" + "".join({v: k for k, v in TABLE.items()}[c] for c in commands)
    return "0" * int(bits, 2)


def reference(code, stdin, cap):
    # Exhausted input stores 0 (the wiki's cat example: "EOF returns 0"),
    # i.e. it reads NUL without moving the cursor.
    result = brainfuck(decode(code), stdin + "\x00" * cap, cap)
    output, tape, ptr, pc, consumed, halted, error = result
    assert error is None
    return output, tape, ptr, pc, min(consumed, len(stdin)), halted


def corpus():
    yield from ("0" * zeros for zeros in range(1024))
    yield from [
        encode(",[.,]"),
        # Five commands is 16 bits: at most 65535 zero digits.
        encode("+[-]."),
        encode("-[>]<"),
        encode(">+<-."),
        encode("+[.,]"),
        "00\n" + "0" * 106,
        " 0\t0 ",
        "0x",
        "1",
        "O",
        "0☃",
        "\n",
    ]


def observe(code, stdin, cap):
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
    assert vm_view(machine, "memory") == list(machine.tape)
    assert vm_view(machine, "stack") == []
    assert machine.input_position() == io.position()
    result = (
        io.getvalue(),
        machine.tape,
        machine.ptr,
        vm_view(machine, "ip"),
        io.position(),
        machine.halted,
    )
    if machine.halted:
        snapshot = machine.snapshot()
        machine.step()
        machine.step()
        assert machine.snapshot() == snapshot
        assert io.getvalue() == result[0]
    return result


def kind(error):
    # Decoding errors versus the Brainfuck oracle's bracket errors.
    return "Unary" if str(error).startswith("Unary") else "unmatched"


def check(code, stdin, cap):
    try:
        expected = reference(code, stdin, cap)
    except ValueError as error:
        with pytest.raises(ValueError, match=kind(error)):
            _Machine(code, ScriptedIO(stdin))
    else:
        assert observe(code, stdin, cap) == expected, (code[:20], len(code), stdin, cap)


@pytest.mark.parametrize("stdin", ["", "AB", "Āā😀\n\xff"])
@pytest.mark.parametrize("cap", [0, 1, 2, 7, 80])
def test_bounded_states_match_independent_decoding(stdin, cap):
    for code in corpus():
        check(code, stdin, cap)


@pytest.mark.parametrize("stdin", ["", "AB"])
def test_run_matches_independent_decoding(stdin):
    for code in corpus():
        try:
            expected = reference(code, stdin, 2000)
        except ValueError as error:
            with pytest.raises(ValueError, match=kind(error)):
                run(code, ScriptedIO(stdin))
            continue
        if expected[5]:
            io = ScriptedIO(stdin)
            run(code, io)
            assert (io.getvalue(), io.position()) == (expected[0], expected[4]), code[
                :20
            ]


def test_every_three_command_program_round_trips():
    for length in range(4):
        for commands in itertools.product("><+-.,[]", repeat=length):
            assert decode(encode(commands)) == "".join(commands)


@pytest.mark.parametrize(
    ("zeros", "brainfuck_code", "stdin", "output"),
    [
        # "1001 in binary becomes 000000000 in unary".
        (9, "<", "", ""),
        # "Program that gets a single character and outputs it again".
        (108, ",.", "Z", "Z"),
        # "Cat program, EOF returns 0": 56623 zero digits.
        (56623, ",[.,]", "cat\n", "cat\n"),
        (1, "", "", ""),
    ],
)
def test_reference_positive_controls(zeros, brainfuck_code, stdin, output):
    code = "0" * zeros
    assert decode(code) == brainfuck_code
    expected = reference(code, stdin, 5000)
    assert expected[0] == output
    assert expected[5]
    assert observe(code, stdin, 5000) == expected


def test_wiki_infinite_loop_never_halts():
    # Wiki example with line breaks "added for readability": 6 * 100 + 95.
    code = "\n".join(["0" * 100] * 6 + ["0" * 95])
    assert decode(code) == "+[]"
    expected = reference(code, "", 500)
    assert not expected[5]
    assert observe(code, "", 500) == expected
