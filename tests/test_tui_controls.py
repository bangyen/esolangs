"""Controls and terminal integration for the step-through screen."""

import sys
from unittest.mock import patch

import pytest

import esolangs.debugger as debugger_api
from esolangs.tui import History, render, replay
from esolangs.tui_loop import breakpoint_for, drive
from tests.test_tui import (
    _drive,
    _frame,
    _highlighted,
    _Keys,
    _plain,
    _runs,
    _selected,
)


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


class TestWatchKeys:
    """``w``/``W``: the watched set is editable from inside the screen."""

    def test_w_adds_a_cell_and_the_row_appears(self) -> None:
        keyboard = _drive("+++", "w0\r q")
        # The notice is read on the repaint the Enter earns; it is gone by
        # the next key, the way a status line should be.
        assert any("watching cell 0" in _plain(s) for s in keyboard.screens)
        assert "cell 0: 0 1" in _plain(keyboard.screens[-1])

    def test_several_cells_can_be_watched(self) -> None:
        keyboard = _drive("+>+", "w0\rw1\rq")
        screen = _plain(keyboard.screens[-1])
        assert "cell 0:" in screen
        assert "cell 1:" in screen

    def test_big_w_removes_one(self) -> None:
        keyboard = _drive("+++", "w0\rW0\rq")
        screen = _plain(keyboard.screens[-1])
        assert "no longer watched" in screen
        assert "watch    cell" not in screen

    def test_a_non_number_is_a_notice(self) -> None:
        keyboard = _drive("+++", "wx\rq")
        assert "not a cell index" in _plain(keyboard.screens[-1])


class TestCountAndGoto:
    """Digits, ``g`` and ``G``: getting the selector somewhere in one go."""

    def test_a_count_prefix_walks_the_selector(self) -> None:
        keyboard = _drive("+>-<", "3lq")
        assert _selected(keyboard.screens[-1]) == ["<"]

    def test_a_count_prefix_steps_that_far(self) -> None:
        assert "step 3" in _drive("+++++", "3 q").headers()[-1]

    def test_big_g_returns_the_selector_to_the_run(self) -> None:
        keyboard = _drive("+>-<", "llGq")
        assert _selected(keyboard.screens[-1]) == ["+"]

    def test_g_prompts_for_a_place(self) -> None:
        keyboard = _drive("+>-<", "g3\rq")
        assert _selected(keyboard.screens[-1]) == ["<"]

    def test_g_to_nowhere_is_a_notice(self) -> None:
        keyboard = _drive("+>-<", "g99\rq")
        assert "no such place" in _plain(keyboard.screens[-1])


class TestHaltPosition:
    """The halted frame rests on the last op, not the start of the file."""

    def test_the_last_op_is_the_highlighted_one(self) -> None:
        frame = replay("brainfuck", "+++", "", 100)
        assert frame.halted
        assert _highlighted(render(frame)) == "+"

    def test_the_pane_stays_at_the_end_of_a_tall_program(self) -> None:
        program = "\n".join("+" for _ in range(100))
        frame = replay("brainfuck", program, "", 10_000)
        plain = _plain(render(frame))
        assert "100 |" in plain
        assert "  1 |" not in plain


class TestPointerFallback:
    """A tape machine that names no state still shows where it points."""

    def test_boolfuck_frames_carry_a_pointer(self) -> None:
        history = History("Boolfuck", "+>", "")
        assert history.at(0).views == (("ptr", "0"),)
        frame = history.at(2)
        assert frame.views == (("ptr", "1"),)
        assert "ptr=1" in render(frame)

    def test_brainfucks_own_views_are_untouched(self) -> None:
        frame = replay("brainfuck", "+", "", 0)
        names = [name for name, _ in frame.views]
        assert "ind" in names
        assert len(names) > 1

    def test_the_debugger_mirrors_the_pointer(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", ">>,", stdin="")
        assert dbg.ptr == 0
        dbg.step()
        assert dbg.ptr == 1


class TestPlayMode:
    """``p``: the loop repaints on a timer until stopped or halted."""

    @staticmethod
    def _poll(answers: list[str | None]) -> object:
        queue = list(answers)
        return lambda _timeout: queue.pop(0) if queue else "q"

    def test_play_advances_on_quiet_timeouts(self) -> None:
        keyboard = _Keys("pq")
        drive(
            History("brainfuck", "+++++", ""),
            keyboard.read,
            keyboard.write,
            poll=self._poll([None, None, "q"]),  # type: ignore[arg-type]
        )
        assert "playing 8/s" in _plain(keyboard.screens[1])
        assert "step 2" in keyboard.headers()[-1]

    def test_play_stops_at_a_breakpoint(self) -> None:
        keyboard = _Keys("pq")
        drive(
            History("brainfuck", "+++++", ""),
            keyboard.read,
            keyboard.write,
            stop=breakpoint_for(cell=(0, 2)),
            poll=self._poll([None, None, None, "q"]),  # type: ignore[arg-type]
        )
        assert "step 2" in keyboard.headers()[-1]

    def test_plus_speeds_play_up(self) -> None:
        keyboard = _Keys("pq")
        drive(
            History("brainfuck", "+++++", ""),
            keyboard.read,
            keyboard.write,
            poll=self._poll(["+", None, "q"]),  # type: ignore[arg-type]
        )
        assert "playing 16/s" in _plain(keyboard.screens[-2])


class TestChangedFlash:
    """The cell the last step touched flashes in the memory row."""

    def test_a_changed_cell_is_styled(self) -> None:
        frame = _frame("+", 0, memory=(1, 2))
        assert _runs(render(frame, changed=frozenset({0})), "33") == ["1"]

    def test_no_flash_without_a_change(self) -> None:
        assert _runs(render(_frame("+", 0, memory=(1, 2))), "33") == []

    def test_stepping_flashes_the_cell_it_wrote(self) -> None:
        keyboard = _drive("++", " q")
        assert "\x1b[1;33m" in keyboard.screens[-1]


class TestRawTerminal:
    """``run_tui`` itself, driven through a pty."""

    # Forks a pty and execs a fresh interpreter, then waits on quiet periods:
    # a subprocess whose cost is a wait, so it stretches under a loaded box.
    @pytest.mark.medium
    @pytest.mark.skipif(sys.platform == "win32", reason="no pty on Windows")
    def test_it_paints_and_quits_on_a_real_terminal(self) -> None:
        import contextlib
        import os
        import pty
        import select
        import signal
        import time

        source = (
            "from esolangs.tui_loop import run_tui\n"
            "run_tui('brainfuck', '+++>++.', '')\n"
        )
        pid, fd = pty.fork()
        if pid == 0:  # pragma: no cover - the child is a fresh interpreter
            os.execv(sys.executable, [sys.executable, "-c", source])

        painted = ""
        deadline = time.time() + 20

        def drain() -> str:
            """Wait for this key's repaint, then read while it keeps coming."""
            out = ""
            quiet = time.time() + 5
            while time.time() < min(quiet, deadline):
                ready, _, _ = select.select([fd], [], [], 0.02)
                if not ready:
                    continue
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                out += chunk.decode("utf-8", "replace")
                quiet = time.time() + 0.05
            return out

        try:
            # The child is a fresh interpreter, so the first paint has to be
            # waited for before any key means anything.
            painted += drain()
            for key in "  q":
                os.write(fd, key.encode())
                painted += drain()
            assert time.time() < deadline, "run_tui did not answer in time"
        finally:
            os.close(fd)
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)

        assert "brainfuck" in painted
        assert "step 2" in painted
        # Raw mode is what makes a bare newline a carriage return too; its
        # absence would mean the terminal was never switched over.
        assert "\r\n" in painted


class TestAgainstTheInterpreter:
    """That the highlighted character is the op the VM is about to run."""

    @pytest.mark.parametrize("step", [0, 5, 11])
    def test_brainfuck_highlight_is_the_next_command(self, step: int) -> None:
        program = "+++>++[<->]<."
        frame = replay("brainfuck", program, "", step)
        marked = _highlighted(render(frame))
        if frame.ip is None:
            pytest.skip("halted with no position")
        assert isinstance(frame.ip, int)
        assert marked == program[frame.ip]
        assert marked in "+-<>[].,"

    def test_a_grid_language_highlight_is_a_real_cell(self) -> None:
        program = "\n".join(["o  v", "   <"])
        frame = _frame(program, (1, 3), language="Clockwise", ip_shape="grid")
        assert _highlighted(render(frame)) == "<"
