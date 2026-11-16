"""Tests for the BASICER interpreter."""

from pathlib import Path

import pytest

from esolangs import Language
from esolangs.exceptions import ArgumentError, HaltError
from esolangs.languages.basicer.interpreter import run
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.runner import native_runner
from tests.support.cli_support import run_cli
from tests.support.vm_support import assert_rejected_output_retry

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


_out = native_runner(run)


def _sums(stdin: str) -> str:
    return "".join(
        line for line in _out(ADDER, stdin).splitlines() if "please" not in line
    )


def test_adder_adds_least_significant_first() -> None:
    from esolangs.languages.basicer.tests.oracle_checks import check_raw_basicer

    check_raw_basicer()
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


def test_numbered_and_unnumbered_jump_targets(monkeypatch, tmp_path: Path) -> None:
    from esolangs.languages.basicer import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "BASICER",
        "10 GOTO 30\n20 PRINT no\n30 PRINT yes",
        interpreter,
        "_parse",
        monkeypatch,
        cases=(("", "yes\n"), ("", "yes\n"), ("", "yes\n")),
    )
    assert _out("GOTO 3\nPRINT no\nPRINT yes") == "yes\n"
    assert_rejected_output_retry(
        "BASICER",
        "10 PRINT hello",
        "hello\n",
        "hello\n",
        prefix=0,
        monkeypatch=monkeypatch,
        unchanged_if_unwritten=True,
        following_writes=(),
    )

    from tests.support.execution import assert_digit_cap_independent

    label = "9" * 641
    source = f"10 GOTO {label}\n20 PRINT skipped\n{label} PRINT reached"
    assert_digit_cap_independent("BASICER", source, "", "reached\n")

    language = Language("BASICER")
    path = tmp_path / "source"
    for source, expected in (
        ("  PRINT hello   \n\nPRINT   there \t\nPAUSE \t\n", "hello   \n  there \t\n"),
        (
            "  20 PRINT   \t\r\n\r\n10 PRINT hello \t\r\n30 CLEAR \t\r\n",
            "hello \t\n  \t\n",
        ),
    ):
        path.write_bytes(source.encode())
        assert language.run(path).output == expected
        assert language.run(path, isolated=True).output == expected
        cli = run_cli("run", language.name, str(path))
        assert (cli.returncode, cli.stdout, cli.stderr) == (0, expected, "")


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


def test_bad_choices_keep_the_rejected_input() -> None:
    from esolangs import ExecutionLimits, Language

    with pytest.raises(ArgumentError):
        _out("GOTO 1 2", "x\n")
    with pytest.raises(HaltError):
        _out("GOTO 1 2", "3\n")

    api = Language("BASICER")
    source = "10 GOTO 20 30\n20 PRINT one\n30 PRINT two"
    limits = ExecutionLimits(max_steps=5)
    for choice, kind, message in (
        ("--1", ArgumentError, "menu choice '--1' is not an integer"),
        ("²", ArgumentError, "menu choice '²' is not an integer"),
        ("3", HaltError, "outside 1 to 2"),
        ("9" * 5001, HaltError, "outside 1 to 2"),
    ):
        dbg = api.make_debugger(source, stdin=choice + "\n1\n")
        with pytest.raises(kind, match=message) as first:
            dbg.run(limits=limits)
        boundary = dbg.snapshot()
        with pytest.raises(kind, match=message) as repeated:
            dbg.run(limits=limits)
        assert first.value is not repeated.value
        assert first.value.observation.input_reads == 1
        assert repeated.value.observation == first.value.observation
        assert dbg.snapshot() == boundary
    assert api.run(source, stdin="\u0661\n", limits=limits).output == "one\ntwo\n"
