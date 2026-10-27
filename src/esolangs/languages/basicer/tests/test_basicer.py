"""Tests for the BASICER interpreter."""

import pytest

from esolangs.exceptions import ArgumentError, HaltError
from esolangs.languages.basicer.interpreter import run
from esolangs.runtime.io import ScriptedIO

ADDER = """10 PRINT First digit please! (1 = 0, 2 = 1, 3 = exit)
20 GOTO 50 70 200
30 PRINT First digit please! (1 = 0, 2 = 1, 3 = exit)
40 GOTO 70 90 190
50 PRINT Second digit please! (1 = 0, 2 = 1)
60 GOTO 110 130
70 PRINT Second digit please! (1 = 0, 2 = 1)
80 GOTO 130 150
90 PRINT Second digit please! (1 = 0, 2 = 1)
100 GOTO 150 170
110 PRINT 0
120 GOTO 10
130 PRINT 1
140 GOTO 10
150 PRINT 0
160 GOTO 30
170 PRINT 1
180 GOTO 30
190 PRINT 1"""

RPG = """10 CLEAR
20 PRINT You wake up in a dark room! What do you do?
30 PRINT 1) Go to the door towards the south
40 PRINT 2) Go to the door towards the north
50 GOTO 60 110
60 CLEAR
70 PRINT The door closes behind you, and all of a sudden,
80 PRINT you fall asleep on the most comfortable bed ever.
90 PAUSE
100 GOTO 10
110 CLEAR
120 PRINT You have escaped the room and are now outside!
130 PRINT Press any key to play again.
140 PAUSE
150 GOTO 10"""


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def _sums(stdin: str) -> str:
    return "".join(
        line for line in _out(ADDER, stdin).splitlines() if "please" not in line
    )


def test_adder_adds_least_significant_first() -> None:
    # 1 + 1 = 10 and 3 + 1 = 100, low bits first.
    assert _sums("2\n2\n3\n") == "01"
    assert _sums("2\n2\n2\n1\n3\n") == "001"


def test_rpg_menu_branches_and_loops() -> None:
    with pytest.raises(EOFError):
        _out(RPG, "2\n")
    io = ScriptedIO("2\n")
    with pytest.raises(EOFError):
        run(RPG, io)
    assert "escaped" in io.getvalue()


def test_unnumbered_lines_count_from_one() -> None:
    assert _out("GOTO 3\nPRINT no\nPRINT yes") == "yes\n"


def test_plot_validates_its_operands() -> None:
    assert _out("PLOT 99 0 #00ff00\nPRINT ok") == "ok\n"
    with pytest.raises(ValueError, match="cannot parse"):
        _out("PLOT 100 0 #00ff00")


@pytest.mark.parametrize(
    ("code", "match"),
    [("10 PRINT a\nPRINT b", "some lines"), ("1 CLEAR\n1 CLEAR", "duplicate")],
)
def test_malformed_programs(code: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        _out(code)


def test_bad_choices() -> None:
    with pytest.raises(ArgumentError):
        _out("GOTO 1 2", "x\n")
    with pytest.raises(HaltError):
        _out("GOTO 1 2", "3\n")
