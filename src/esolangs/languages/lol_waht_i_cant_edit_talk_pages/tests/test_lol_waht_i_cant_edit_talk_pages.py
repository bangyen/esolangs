"""Tests for the lol waht i cant edit talk pages interpreter: the page's examples."""

import pytest

from esolangs import Language
from esolangs.exceptions import HaltError, InputExhaustedError
from esolangs.languages.lol_waht_i_cant_edit_talk_pages import interpreter as native
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.runner import native_runner
from tests.support.prepared_support import check_image_reuse
from tests.support.vm_support import assert_rejected_input_retry

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


_out = native_runner(native.run)


def _steps(code: str, stdin: str, count: int) -> str:
    """Run ``count`` statements of a program that never halts."""
    io = ScriptedIO(stdin)
    machine = native._Machine(code, io)
    for _ in range(count):
        machine.step()
    assert not machine.halted
    return io.getvalue()


def test_truth_machine() -> None:
    from esolangs.languages.lol_waht_i_cant_edit_talk_pages.tests.oracle_checks import (
        check_raw_lol_waht_i_cant_edit_talk_pages,
    )

    check_raw_lol_waht_i_cant_edit_talk_pages()
    assert _out(TRUTH, "0") == "0"
    assert _steps(TRUTH, "1", 20).startswith("1111")


def test_cat_loops_on_itself() -> None:
    assert _steps(CAT, "7", 20).startswith("777")


@pytest.mark.parametrize("code", [APLUSB, MINIFIED])
def test_a_plus_b(code: str) -> None:
    assert _out(code, "3 4") == "7"


def test_output_a(monkeypatch: pytest.MonkeyPatch) -> None:
    code = "user:A\nedit user talk:A to change 65 messages\ngrr why u do this A"
    assert _out(code + "\nwaht i got banned") == "A"
    check_image_reuse(
        "lol waht i cant edit talk pages",
        code + "\nwaht i got banned",
        native,
        "_parse",
        monkeypatch,
        cases=(("", "A"),) * 3,
    )


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


_READ_Q = "im awesome tottaly but no q"
_READ_AND_PRINT = f"user:q\n{_READ_Q}\ni hate u q"


@pytest.mark.medium
def test_rejected_numeric_input_survives_retry() -> None:
    assert_rejected_input_retry(
        "lol waht i cant edit talk pages",
        _READ_AND_PRINT,
        "oops 7",
        "7",
        "7",
        position=4,
        reads=1,
        prefix=1,
    )


def test_an_undefined_read_target_retains_the_first_fault() -> None:
    api = Language("lol waht i cant edit talk pages")
    dbg = api.make_debugger(_READ_Q, stdin="5 7")
    for _ in range(3):
        with pytest.raises(HaltError, match="variable 'q' is not defined"):
            dbg.step()
        result = dbg.observation
        assert (dbg.ip, result.steps, result.input_position, result.input_reads) == (
            0,
            0,
            1,
            1,
        )
    assert api.run(_READ_AND_PRINT, stdin="5 7").output == "5"
