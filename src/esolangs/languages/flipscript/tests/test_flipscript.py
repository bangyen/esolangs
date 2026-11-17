"""Tests for the Flipscript interpreter."""

import pytest

from esolangs.exceptions import (
    ArgumentError,
    HaltError,
    InputExhaustedError,
    ProgramError,
)
from esolangs.languages.flipscript.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO

_PARITY = (
    "start(0)\nnum INPUT = input\nnum ISEVEN = INPUT%2\nup stop\n"
    'up output("The number is even",new)\nflip(ISEVEN==0)\n'
    'output("The number is odd",new)'
)
_PASSWORD = (
    "start(0)\nstring PASSWORD = input\nnum SECRETCODE = input\nup stop\n"
    'up output("Access Denied!",new)\n'
    'down flip("Password123"$!=PASSWORD||SECRETCODE!=123)\n'
    'output("Secret data!",new)'
)
_JUMP = 'start(0)\nnum JUMP = input\njump JUMP\noutput("1",new)\noutput("2",new)'


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_the_pages_examples() -> None:
    # Statement examples get a start line; the page shows them bare.
    assert (
        _out('start(0)\noutput("Hello"," World!",new,"6 + 7 is equal to: ",6+7,new)')
        == "Hello World!\n6 + 7 is equal to: 13\n"
    )
    assert _out("start(0)\noutput(8+2*10)") == "100"
    assert _out(_PARITY, "4\n") == "The number is even\n"
    assert _out(_PARITY, "5\n") == "The number is odd\n"
    assert _out(_PASSWORD, "Password123\n123\n") == "Secret data!\n"
    assert _out(_PASSWORD, "Password123\n124\n") == "Access Denied!\n"
    assert _out(_PASSWORD, "password123\n123\n") == "Access Denied!\n"
    comments = (
        "This program was written by Bob the Builder!\nstart(0)\n"
        'num ONE = input\nnum TWO = input\noutput(ONE," + ",TWO," = ",ONE+TWO,new)'
    )
    assert _out(comments, "2\n3\n") == "2 + 3 = 5\n"
    assert [_out(_JUMP, f"{k}\n") for k in (1, 2, 3)] == ["1\n2\n", "2\n", ""]


def test_the_array_example_fills_ten_cells() -> None:
    machine = _Machine(
        "start(0)\nnum I = 0\nup flip(1==1)\ndown num ARRAY(I) = I\n"
        "down num I = I+1\nflip(I<10)",
        ScriptedIO(),
    )
    while not machine.halted:
        machine.step()
    assert machine.env == {
        "I": ("num", 10.0),
        **{f"ARRAY{k}": ("num", float(k)) for k in range(10)},
    }


@pytest.mark.parametrize(
    ("code", "stdin", "expected"),
    [
        # The topmost start wins; start(1) runs up and halts off the top.
        ('output("a")\nstart(1)\nstart(0)\noutput("b")', "", "a"),
        # decay(2): the first two encounters run, a failed guard is no encounter.
        (
            'start(0)\nnum I = 0\nup flip(1==1)\ndown decay(2) output("d")\n'
            "down num I = I+1\nflip(I<4)",
            "",
            "dd",
        ),
        ('start(0)\ndecay(0) output("x")\noutput("y")', "", "y"),
        # Strictly left to right, both for math and for || and &&.
        ("start(0)\nflip(1==1||1==0&&1==0)\noutput(1)", "", "1"),
        ("start(0)\nflip(1==0&&1==0||1==1)\noutput(1)", "", ""),
        ("start(0)\noutput(0-7%3,new,7/2,new,1/4)", "", "2\n3.5\n0.25"),
        ('start(0)\nstring S = input\noutput(S,"|")', " a b \r\n", " a b |"),
        ("start(0)\nnum N = input\noutput(N+1)", " -1.5 \n", "-0.5"),
        ("start(0)\n\n   \nstop\noutput(1)", "", ""),
        ("start(0)\nnum N(1+1) = 5\noutput(N(2))", "", "5"),
        # A guarded line is not checked while its guard fails.
        ("start(0)\nup nonsense here\noutput(1)", "", "1"),
    ],
)
def test_rulings(code: str, stdin: str, expected: str) -> None:
    assert _out(code, stdin) == expected


@pytest.mark.parametrize(
    ("code", "stdin", "error"),
    [
        ('output("x")', "", ProgramError),
        ("start(2)", "", ProgramError),
        ("start(0)\nfoo", "", ProgramError),
        ("start(0)\nup start(0)", "", ProgramError),
        ("start(0)\nup down stop", "", ProgramError),
        ("start(0)\noutput(1 + 2)", "", ProgramError),
        ("start(0)\n" + "x" * 4001, "", ProgramError),
        ("start(0)\noutput(X)", "", HaltError),
        ('start(0)\nnum X = "a"', "", HaltError),
        ('start(0)\nnum X = 1\nstring X = "a"', "", HaltError),
        ('start(0)\nflip("a"==1)', "", HaltError),
        ("start(0)\noutput(1/0)", "", HaltError),
        ("start(0)\noutput(1%0)", "", HaltError),
        ("start(0)\njump 0", "", HaltError),
        ("start(0)\njump 1.5", "", HaltError),
        ("start(0)\ndecay(1.5) stop", "", HaltError),
        ("start(0)\nnum X = input", "", InputExhaustedError),
        ("start(0)\nnum X = input", "1e3\n", ArgumentError),
    ],
)
def test_errors(code: str, stdin: str, error: type[Exception]) -> None:
    with pytest.raises(error):
        _out(code, stdin)


def test_a_jump_past_the_file_halts() -> None:
    assert _out('start(0)\njump 65536\noutput("x")') == ""
