"""Tests for the IEBEL interpreter, pinned to the wiki's examples."""

import pytest

from esolangs.languages.iebel.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO

HELLO = """0:1 72 0
1:1 2 -2
2:2 69 0
3:2 3 -2
4:3 76 0
5:3 4 -2
6:3 4 -2
7:4 79 0
8:4 5 -2
9:5 32 0
10:5 6 -2
11:6 87 0
12:6 7 -2
13:4 5 -2
14:7 82 0
15:7 8 -2
16:3 4 -2
17:8 68 0
18:8 9 -2
19:0 0 -1"""

TRUTH = """0:0 0 -3
1:48 48 0
2:0 48 5
3:0 1 -2
4:0 0 -1
5:0 1 -2
6:0 1 5"""


def test_hello_world() -> None:
    io = ScriptedIO()
    run(HELLO, io)
    assert io.getvalue() == "HELLO WORLD"


def test_truth_machine_zero() -> None:
    io = ScriptedIO("0")
    run(TRUTH, io)
    assert io.getvalue() == "0"


def test_truth_machine_one_loops() -> None:
    machine = _Machine(TRUTH, ScriptedIO("1"))
    for _ in range(20):
        machine.step()
    assert machine.io.getvalue() == "1" * 9


def test_increment_and_decrement_wrap() -> None:
    # -4 takes register 2 below zero; -5 then brings register 3 to 1.
    io = ScriptedIO()
    run("1 2 -4\n2 0 -2\n0 3 -5\n3 0 -2", io)
    assert io.getvalue() == chr(255) + chr(1)


@pytest.mark.parametrize(
    ("code", "match"),
    [
        ("1 2", "three"),
        ("0 256 0", "range"),
        ("0 0 -6", "range"),
        ("3:0 0 0", "numbered"),
    ],
)
def test_malformed_programs(code: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        run(code, ScriptedIO())
