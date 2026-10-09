"""Nope. through the shared API, CLI and machinery."""

from unittest.mock import patch

from esolangs.tui import History
from esolangs.tui_loop import drive
from tests.test_tui import _Keys, _plain


class TestRestartKey:
    """``R``: a fresh run without leaving the screen."""

    def test_r_alone_restarts_on_the_same_stdin(self) -> None:
        keyboard = _Keys("rR\rq")
        drive(History("brainfuck", ",.", "A"), keyboard.read, keyboard.write)
        # After the run the prompt offers the running stdin back; Enter
        # takes it, and the repaint is step 0 with nothing written yet.
        assert "restarted" in _plain(keyboard.screens[-1])
        assert "step 0" in keyboard.headers()[-1]

    def test_the_stdin_can_be_edited_before_restarting(self) -> None:
        keyboard = _Keys("R\x7fB\rrq")
        drive(History("brainfuck", ",.", "A"), keyboard.read, keyboard.write)
        assert "'B'" in _plain(keyboard.screens[-1])

    def test_escape_keeps_the_run_being_debugged(self) -> None:
        keyboard = _Keys(" R\x1bq")
        drive(History("brainfuck", "+++", ""), keyboard.read, keyboard.write)
        assert "step 1" in keyboard.headers()[-1]

    def test_a_refused_stdin_is_a_notice_not_a_crash(self) -> None:
        keyboard = _Keys("R\rq")
        history = History("brainfuck", "+++", "")
        with patch("esolangs.tui.make_debugger", side_effect=ValueError("nope")):
            drive(history, keyboard.read, keyboard.write)
        assert "restart failed" in _plain(keyboard.screens[-1])

    def test_restart_rewinds_the_history(self) -> None:
        history = History("brainfuck", "+++", "")
        history.at(3)
        history.restart("")
        assert history.top == 0
        assert history.at(0).step == 0
        assert history.stdin == ""
