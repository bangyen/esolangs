"""Tests for the lol waht i cant edit talk pages interpreter: the page's examples."""

import pytest

from esolangs.exceptions import HaltError, InputExhaustedError
from esolangs.languages.lol_waht_i_cant_edit_talk_pages.interpreter import (
    _Machine,
    run,
)
from esolangs.runtime.io import ScriptedIO

TRUTH = """user:i
im awesome tottaly but no i
i hate u i
JUST LET ME CHANGE 1 MESSAGE ON i {
i hate u i
}
waht i got banned"""

CAT = """user:autocorrect
im awesome tottaly but no autocorrect
JUST LET ME CHANGE AUTOCORRECT MESSAGES ON AUTOCORRECT {
i hate you autocorrect
}
waht i got banned"""

APLUSB = """User:用户1
User:用户2
im awesome tottaly but no 用户1
im awesome tottaly but no 用户2
User:用户3
edit user talk:用户3 to change 用户1 messages
edit user talk:用户3 to change 用户2 messages
i hate u 用户3
waht i got banned"""

MINIFIED = """user:A
user:B
im awesome tottaly but no A
im awesome tottaly but no B
edit user talk:A to change B messages
i hate u A
waht i got banned"""


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def _steps(code: str, stdin: str, count: int) -> str:
    """Run ``count`` statements of a program that never halts."""
    io = ScriptedIO(stdin)
    machine = _Machine(code, io)
    for _ in range(count):
        machine.step()
    assert not machine.halted
    return io.getvalue()


def test_truth_machine() -> None:
    assert _out(TRUTH, "0") == "0"
    assert _steps(TRUTH, "1", 20).startswith("1111")


def test_cat_loops_on_itself() -> None:
    assert _steps(CAT, "7", 20).startswith("777")


@pytest.mark.parametrize("code", [APLUSB, MINIFIED])
def test_a_plus_b(code: str) -> None:
    assert _out(code, "3 4") == "7"


def test_output_a() -> None:
    code = "user:A\nedit user talk:A to change 65 messages\ngrr why u do this A"
    assert _out(code + "\nwaht i got banned") == "A"


def test_hello_world_signature() -> None:
    code = "Hello, world! --tommyaweosme 14:39, 7 January 2024\nwaht i got banned"
    assert _out(code) == "Hello, world!"


def test_empty_program_and_no() -> None:
    assert _out("waht i got banned") == ""
    code = "user:a\nedit user talk:a to remove no messages\ni hate u a"
    assert _out(code) == "0"


def test_errors() -> None:
    with pytest.raises(ValueError, match="unknown"):
        _out("hello")
    with pytest.raises(HaltError, match="not defined"):
        _out("i hate u q")
    with pytest.raises(InputExhaustedError):
        _out("user:a\nim awesome tottaly but no a")
