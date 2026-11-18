"""Tests for the GridScript interpreter, against the page's sample programs."""

import re
from pathlib import Path

import pytest

from esolangs.exceptions import HaltError, ProgramError
from esolangs.languages.gridscript.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO

_HEAD = "#T.\n@width 3\n@height 1\n(1,1):START\n"


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def _prefix(code: str, steps: int, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    for _ in range(steps):
        machine.step()
    return io.getvalue()


_TRUTH = (
    "#TRUTH MACHINE.\n@width 9\n@height 5\n(1,1):START\n(3,1):INPUT INT\n"
    "(5,1):GO EAST\n(7,1):SWITCH =1\n(7,3):PRINT 1\n(7,5):GO WEST\n"
    "(5,5):GO NORTH\n(9,1):PRINT 0\n"
)
_FACTORIAL = (
    "#FACTORIAL.\n@width 14\n@height 8\n(1,3):START\n(7,1):CHECKPOINT 0\n"
    "(3,3):INPUT INT TO n\n(5,3):STORE n\n(7,3):GO EAST\n(9,3):DECREMENT n\n"
    "(11,3):SWITCH n\n(11,5):MULTIPLY BY n\n(11,7):GOTO 0\n(13,3):PRINT\n"
)
_ACK = (
    "#ACKERMANN FUNCTION.\n@width 9\n@height 1\n(1,1):START\n(3,1):INPUT INT TO x\n"
    "(5,1):INPUT INT TO y\n(7,1):CALL ACK WITH ARGUMENTS x y\n(9,1):PRINT\n\n"
    "##ACK.\n@width 19\n@height 7\n(1,1):START\n(3,1):INPUT INT TO x\n"
    "(5,1):INPUT INT TO y\n(7,1):SWITCH !x\n(7,3):INCREMENT y\n(7,5):RETURN y\n"
    "(9,1):SWITCH !y\n(9,3):DECREMENT x\n(9,5):CALL ACK WITH ARGUMENTS x 1\n"
    "(9,7):RETURN\n(11,1):DECREMENT y\n(13,1):CALL ACK WITH ARGUMENTS x y GIVING z\n"
    "(15,1):DECREMENT x\n(17,1):CALL ACK WITH ARGUMENTS x z\n(19,1):RETURN\n"
)


def test_the_pages_sample_programs() -> None:
    assert _out(_HEAD.replace("START\n", "START\n(3,1):PRINT 'Hello World'\n")) == (
        "Hello World"
    )
    cat = (
        "#CAT PROGRAM.\n@width 11\n@height 1\n(1,1):START\n(3,1):CHECKPOINT 0\n"
        "(5,1):INPUT STRING s\n(7,1):SWITCH !s\n(9,1):PRINT s\n(11,1):GOTO 0\n"
    )
    # "halts when either 0 or the empty string is given"
    assert _out(cat, "ab\ncd\n0\nef\n") == "abcd"
    assert _out(cat, "ab\n\n") == "ab"
    assert _out(_TRUTH, "0\n") == "0"
    assert _prefix(_TRUTH, 200, "1\n") == "1" * 12
    assert _out(_FACTORIAL, "5\n") == "120"
    assert [_out(_ACK, f"{x}\n{y}\n") for x, y in ((0, 0), (1, 2), (2, 3))] == [
        "1",
        "4",
        "9",
    ]
    fibonacci = (
        "#FIBONACCI SEQUENCE.\n@width 37\n@height 1\n@datawidth 10000\n"
        "@dataheight 1\n(1,1):START\n(3,1):STORE 1\n(5,1):NEXT VALUE\n"
        '(7,1):STORE 1\n(9,1):NEXT VALUE\n(11,1):PRINT "1 1"\n(13,1):CHECKPOINT 0\n'
        "(15,1):PREVIOUS VALUE\n(17,1):PREVIOUS VALUE\n(19,1):STORE TO a\n"
        "(21,1):NEXT VALUE\n(23,1):STORE TO b\n(25,1):INCREMENT a BY b GIVING c\n"
        '(27,1):PRINT " "\n(29,1):NEXT VALUE\n(31,1):STORE c\n(33,1):PRINT\n'
        "(35,1):NEXT VALUE\n(37,1):GOTO 0\n"
    )
    assert _prefix(fibonacci, 400).startswith("1 1 2 3 5 8 13 21 34 55 89 ")
    with pytest.raises(HaltError, match="32-bit"):  # fib(47) passes 2^31
        _out(fibonacci)


def test_a_node_holds_the_tracer_only_strictly_inside() -> None:
    # 99 Bottles turns north at x=6 under "<= radius" and re-enters the
    # DECREMENT column at x=7; strictly inside, it ends the song.
    wiki = Path(__file__).with_name("bottles.gs").read_text()
    song = _out(wiki)
    assert song.startswith(
        "99 bottles of beer on the wall,\n99 bottles of beer.\n"
        "Take one down and pass it around,\n99 bottles of beer on the wall!\n\n98"
    )
    assert song.endswith(
        "1 bottle of beer\nTake one down and pass it around,\n"
        "No more bottles of beer on the wall."
    )
    assert len(re.findall("Take one down", song)) == 100
    radius = "#R.\n@width 4\n@height 1\n@radius 2\n(1,1):START\n(3,1):PRINT 1\n"
    assert _out(radius) == "1"  # at x=2, distance 1 < 2


def test_values_casts_and_the_buffer() -> None:
    cases = [
        ("STORE 7\n(2,1):DIVIDE BY -2\n(2,1):PRINT", "-3"),  # truncates
        ("STORE 1.5 TO f\n(2,1):MULTIPLY f BY 2\n(2,1):PRINT f", "3.0"),
        ("STORE '12' TO s\n(2,1):INCREMENT s BY 1\n(2,1):PRINT s", "13"),
        (
            "SPLIT 'a 7 c'\n(2,1):REMOVE 1\n(2,1):PRINT\n(2,1):REMOVE TOP TO t\n"
            "(2,1):PRINT t\n(2,1):REMOVE TO u\n(2,1):PRINT u",
            "7ca",
        ),
        (
            "STORE 2\n(2,1):SPLIT 'x y z'\n"
            "(2,1):REMOVE THIS POSITION TO v\n(2,1):PRINT v",
            "z",
        ),
        ("REMOVE TO w\n(2,1):PRINT w\n(2,1):SWITCH w\n(2,1):PRINT TRUE", "TRUE"),
    ]
    for body, expected in cases:
        assert _out(_HEAD.replace("(1,1):START\n", f"(1,1):START\n(2,1):{body}\n")) == (
            expected
        ), body
    leave = "##F.\n(1,1):START\n(2,1):STORE 4\n"
    code = _HEAD + "(2,1):CALL F GIVING r\n(2,1):PRINT r\n(2,1):PRINT 5\n\n" + leave
    assert _out(code) == "5"  # leaving the space returns nothing: r is NULL


def test_errors() -> None:
    cases = [
        (_HEAD + "(2,1):GO RANDOM", ProgramError),  # never exercised
        ("#T.\n@width 3\n(1,1):START", ProgramError),  # no @height
        (_HEAD + "(2,1):RETURN", ProgramError),  # RETURN outside a subroutine
        (_HEAD + "(2,1):STORE 2147483647\n(2,1):INCREMENT", HaltError),
    ]
    for code, error in cases:
        with pytest.raises(error):
            _out(code)
