"""Tests for the step-through screen.

Everything here drives :func:`~esolangs.tui.render`, the position adapter
under it, the retained history, and the key loop -- which takes its input
and output as arguments, so it can be run with scripted keys in process.
Only ``run_tui``'s raw-mode wrapper around the terminal is left out, and one
test drives even that through a pty.
"""

import re
import sys
from unittest.mock import patch

import pytest

import esolangs
from esolangs.tui import (
    CLEAR,
    Frame,
    History,
    Mark,
    _cells,
    at_cell,
    breakpoint_for,
    drive,
    grid,
    locate,
    render,
    replay,
)

#: Any styled run: its SGR parameters, and the text they cover.
_STYLED = re.compile("\x1b\\[([0-9;]+)m(.*?)\x1b\\[0m")


def _frame(
    program: str,
    ip: int | tuple[int, ...] | None,
    *,
    language: str = "brainfuck",
    step: int = 0,
    halted: bool = False,
    memory: tuple[int, ...] = (),
    stack: tuple[object, ...] = (),
    output: str = "",
    fault: str | None = None,
    ip_shape: str = "offset",
    views: tuple[tuple[str, str], ...] = (),
) -> Frame:
    """Build a frame from the few fields a screen test actually varies."""
    return Frame(
        language=language,
        program=program,
        ip=ip,
        step=step,
        halted=halted,
        memory=memory,
        stack=stack,
        output=output,
        fault=fault,
        ip_shape=ip_shape,
        views=views,
    )


#: Reverse video is the running position, red a breakpoint, and an
#: underline the selector; bold is added where the first two meet, since
#: reverse over red is another mostly-red cell.  They compose, so a run is
#: described by which parameters it carries rather than by a fixed code.
_RUN, _BREAK, _PICK = "7", "41", "4"


def _runs(screen: str, *want: str, without: str = "") -> list[str]:
    """The text of every run whose style carries all of ``want``."""
    return [
        text
        for code, text in _STYLED.findall(screen)
        if set(want) <= set(code.split(";"))
        and (not without or without not in code.split(";"))
    ]


def _sgr(screen: str) -> frozenset[str]:
    """The distinct styles the screen uses."""
    return frozenset(code for code, _ in _STYLED.findall(screen))


def _marked_break(screen: str) -> list[str]:
    """Runs painted as a breakpoint the run is not standing on."""
    return _runs(screen, _BREAK, without=_RUN)


def _marked_both(screen: str) -> list[str]:
    """Runs that are the running position *and* a breakpoint."""
    return _runs(screen, _BREAK, _RUN)


def _selected(screen: str) -> list[str]:
    """Runs under the selector."""
    return _runs(screen, _PICK)


def _highlighted(screen: str) -> str | None:
    """The one character marked as the running position, or ``None``."""
    found = _runs(screen, _RUN, without=_BREAK)
    assert len(found) <= 1, f"expected at most one highlight, got {found}"
    return found[0] if found else None


def _plain(screen: str) -> str:
    """``screen`` with every marking removed, leaving the characters."""
    return _STYLED.sub(r"\2", screen)


class TestGrid:
    def test_ragged_lines_are_padded_to_a_rectangle(self) -> None:
        # The trailing blanks are not in the file, but a grid language steps
        # over them, so the rows have to be equal width before a column can
        # be bounds-checked.
        assert grid("ab\nc\n") == ["ab", "c "]

    def test_empty_program_is_one_empty_row(self) -> None:
        assert grid("") == [""]


class TestLocateOffset:
    """The default: ``ip`` counts characters into the program text."""

    def test_int_is_an_offset(self) -> None:
        assert locate("abc", 2) == Mark(0, 2)

    def test_offset_counts_past_a_newline(self) -> None:
        assert locate("ab\ncd", 4) == Mark(1, 1)

    def test_offset_of_a_newline_itself_ends_its_row(self) -> None:
        assert locate("ab\ncd", 2) == Mark(0, 2)

    def test_it_marks_a_single_character(self) -> None:
        assert locate("abc", 1).span == 1

    def test_past_the_text_is_not_located(self) -> None:
        assert locate("abc", 99) is None

    def test_negative_is_not_located(self) -> None:
        assert locate("abc", -1) is None

    def test_none_is_not_located(self) -> None:
        assert locate("abc", None) is None

    def test_a_bool_is_not_a_position(self) -> None:
        # bool is an int subclass, and True would otherwise read as offset 1.
        flag = True
        assert locate("abc", flag) is None

    def test_a_tuple_under_the_default_is_not_located(self) -> None:
        # This is the whole safety of the trait: a language that reports a
        # tuple without saying what it counts gets no highlight, because a
        # frame stack and a cell are indistinguishable by value.
        assert locate("abcdef", (1, 2)) is None
        assert locate("abcdef", (2,)) is None
        assert locate("abcdef", (0, 0, 0, 1, 0, 0)) is None


class TestLocateGrid:
    """``ip`` is a cell of the rectangle, with any rest a heading."""

    def test_it_uses_the_first_two_parts(self) -> None:
        assert locate("ab\ncd", (1, 0, 3), "grid") == Mark(1, 0)

    @pytest.mark.parametrize(
        "ip", [(1, 1), (1, 1, 2), (1, 1, 2, 0), (1, 1, 0, 0, 1, 1)]
    )
    def test_any_width_of_heading_is_accepted(self, ip: tuple[int, ...]) -> None:
        # COD flattens one four-tuple per live cod, so a grid position is
        # not a fixed width; the first two parts are what matters.
        assert locate("ab\ncd", ip, "grid") == Mark(1, 1)

    def test_it_may_sit_past_its_own_ragged_line(self) -> None:
        # Row 1 is one character long in the file; the rectangle is two wide,
        # and column 1 is a real position the interpreter can occupy.
        assert locate("ab\nc", (1, 1), "grid") == Mark(1, 1)

    def test_outside_the_rectangle_is_not_located(self) -> None:
        assert locate("ab\ncd", (5, 0), "grid") is None
        assert locate("ab\ncd", (0, 9), "grid") is None

    def test_too_few_parts_is_not_located(self) -> None:
        assert locate("ab\ncd", (1,), "grid") is None

    def test_a_non_integer_coordinate_is_not_located(self) -> None:
        assert locate("abc", ("x", 1), "grid") is None

    def test_an_int_under_grid_is_not_located(self) -> None:
        assert locate("abc", 1, "grid") is None


class TestLocateLine:
    """``ip`` starts with a line number, so the whole line is marked."""

    def test_it_marks_the_named_line(self) -> None:
        assert locate("ab\ncdef", (1,), "line") == Mark(1, 0, 4)

    def test_the_frame_indices_after_it_are_ignored(self) -> None:
        # Interprogck8 appends one index per open frame; the line is still
        # the first part.
        assert locate("ab\ncdef", (1, 7, 2), "line") == Mark(1, 0, 4)

    def test_the_span_covers_the_padded_rectangle(self) -> None:
        # Row 0 is padded out to the widest row, and the mark covers it, so
        # a short line still reads as a whole line.
        assert locate("ab\ncdef", (0,), "line") == Mark(0, 0, 4)

    def test_a_bare_int_is_taken_as_the_line(self) -> None:
        assert locate("ab\ncd", 1, "line") == Mark(1, 0, 2)

    def test_past_the_last_line_is_not_located(self) -> None:
        assert locate("ab\ncd", (9,), "line") is None

    def test_an_empty_tuple_is_not_located(self) -> None:
        assert locate("ab\ncd", (), "line") is None


class TestLocateUnknownShape:
    def test_a_shape_nobody_declares_is_not_located(self) -> None:
        assert locate("abc", 1, "sideways") is None
        assert locate("abc", (1, 1), "sideways") is None


class TestRender:
    def test_highlights_the_character_at_the_ip(self) -> None:
        assert _highlighted(render(_frame("+>-<", 2, memory=(0,)))) == "-"

    def test_highlights_the_right_cell_of_a_grid(self) -> None:
        frame = _frame("abc\ndef", (1, 2), language="Streetcode", ip_shape="grid")
        assert _highlighted(render(frame)) == "f"

    def test_a_grid_tuple_from_a_language_that_says_nothing_is_not_marked(self) -> None:
        # Grapheme's (2, 5) is pc 5 one call deep, not row 2 column 5.  It
        # fits the rectangle, which is exactly why it must not be read.
        frame = _frame("abc\ndef", (1, 2), language="Grapheme")
        assert _highlighted(render(frame)) is None

    def test_a_line_shape_marks_the_whole_line(self) -> None:
        frame = _frame("abc\ndef", (1,), language="Interprogck8", ip_shape="line")
        assert _highlighted(render(frame)) == "def"

    def test_an_unlocatable_ip_leaves_the_program_unmarked(self) -> None:
        screen = render(_frame("abc", None, language="Circuit Diagram"))
        assert _highlighted(screen) is None
        # The raw value is still on the header, which is what makes the
        # missing highlight readable rather than a silent failure.
        assert "ip None" in screen

    def test_header_reports_the_step_and_state(self) -> None:
        frame = _frame("+", 0, step=7, halted=True, memory=(1,), output="hi")
        head = render(frame).splitlines()[0]
        assert "brainfuck" in head
        assert "step 7" in head
        assert "halted" in head

    def test_running_and_halted_are_distinguished(self) -> None:
        assert "running" in render(_frame("+", 0, memory=(0,))).splitlines()[0]

    def test_shows_memory_stack_and_output(self) -> None:
        frame = _frame("+", 0, memory=(1, 2, 3), stack=("x",), output="out")
        screen = render(frame)
        assert "1 2 3" in screen
        assert "'out'" in screen

    def test_an_empty_view_says_so_rather_than_showing_nothing(self) -> None:
        assert "(empty)" in render(_frame("+", 0))

    def test_a_long_tape_is_truncated_with_a_count(self) -> None:
        screen = render(_frame("+", 0, memory=tuple(range(500))))
        assert "more" in screen
        assert all(len(line) <= 80 for line in screen.splitlines())

    def test_a_fault_is_shown_when_present(self) -> None:
        frame = _frame("+", 0, step=1, memory=(0,), fault="ValueError: bad")
        assert "ValueError: bad" in render(frame)

    def test_no_fault_row_without_a_fault(self) -> None:
        assert "fault" not in render(_frame("+", 0, step=1, memory=(0,)))

    def test_it_shows_the_names_the_language_gives_its_state(self) -> None:
        frame = _frame("+", 0, views=(("acc", "3"), ("ptr", "0")))
        screen = render(frame)
        assert "acc=3" in screen
        assert "ptr=0" in screen

    def test_no_views_row_when_the_language_names_nothing(self) -> None:
        assert "views" not in render(_frame("+", 0))

    def test_the_views_row_is_cut_to_the_width(self) -> None:
        frame = _frame("+", 0, views=tuple((f"name{i}", "9" * 20) for i in range(20)))
        assert all(len(line) <= 80 for line in render(frame).splitlines())

    def test_the_views_row_costs_the_program_pane_one_line(self) -> None:
        # The pane shrinks by exactly the row added, rather than the screen
        # growing past the height it was given.
        program = "\n".join("x" for _ in range(40))
        without = render(_frame(program, 0), height=20)
        with_views = render(_frame(program, 0, views=(("acc", "1"),)), height=20)
        assert len(with_views.splitlines()) <= 20
        assert len(with_views.splitlines()) == len(without.splitlines())


class TestWindowing:
    def test_a_tall_program_scrolls_to_keep_the_ip_visible(self) -> None:
        program = "\n".join(f"line{i}" for i in range(200))
        screen = render(_frame(program, program.index("line150")), height=24)
        assert _highlighted(screen) == "l"
        # The highlight splits the word with escapes, so the check is made
        # against the screen with the marking removed.
        assert "line150" in _plain(screen)
        assert "line0 " not in _plain(screen)

    def test_a_wide_program_scrolls_sideways(self) -> None:
        program = "." * 400 + "@" + "." * 400
        screen = render(_frame(program, 400), width=60)
        assert _highlighted(screen) == "@"
        assert all(len(line) <= 60 for line in _plain(screen).splitlines())

    def test_every_row_fits_the_given_width(self) -> None:
        program = "\n".join("x" * 300 for _ in range(80))
        frame = _frame(program, 0, memory=(7,), output="y" * 300)
        screen = render(frame, 20, 70)
        assert all(len(line) <= 70 for line in _plain(screen).splitlines())

    def test_grid_rows_share_one_column_window(self) -> None:
        # A grid language's rows have to stay aligned under each other, so
        # the horizontal window cannot be chosen per line.
        program = "\n".join(f"{i:03d}" + "." * 100 for i in range(5))
        screen = _plain(render(_frame(program, (2, 60)), width=40))
        body = [
            line for line in screen.splitlines() if "|" in line and "step" not in line
        ]
        assert len({len(line) for line in body}) == 1


class TestReplay:
    def test_counts_the_steps_actually_executed(self) -> None:
        # Asking past the halt reports where the program really stopped,
        # which is what lets the back key land on the last real step.
        frame = replay("brainfuck", "++", "", 1_000)
        assert frame.halted
        assert frame.step == 2

    def test_is_deterministic(self) -> None:
        first = replay("brainfuck", "+++>++<-.", "", 5)
        second = replay("brainfuck", "+++>++<-.", "", 5)
        assert (first.memory, first.ip, first.output) == (
            second.memory,
            second.ip,
            second.output,
        )

    def test_stepping_back_is_the_earlier_state(self) -> None:
        assert replay("brainfuck", "+++", "", 2).memory == (2,)
        assert replay("brainfuck", "+++", "", 1).memory == (1,)

    def test_zero_steps_is_the_initial_state(self) -> None:
        frame = replay("brainfuck", "+++", "", 0)
        assert frame.step == 0
        assert frame.memory == (0,)

    def test_a_raising_program_reports_the_fault_instead_of_propagating(self) -> None:
        frame = replay("brainfuck", ",", "", 5)
        assert frame.fault is not None
        # The VM translates what the interpreter raises, so the fault names
        # the package's own exception rather than the bare EOFError.
        assert "InputExhaustedError" in frame.fault

    def test_an_unknown_language_still_raises(self) -> None:
        with pytest.raises(ValueError, match="unknown language"):
            replay("Nonesuch", "+", "", 1)


class TestHistory:
    """That keeping the frames agrees with re-deriving them, and stays bounded."""

    @pytest.mark.parametrize("program", ["+++>++[<->]<.", "++++[>++<-]>.", ",.", "+"])
    def test_every_step_matches_a_replay(self, program: str) -> None:
        # The whole point of keeping frames is that they are the same
        # frames, so the cached path is checked against the derived one at
        # every step rather than only at the ends.
        history = History("brainfuck", program, "")
        for step in range(12):
            assert history.at(step) == replay("brainfuck", program, "", step)

    def test_walking_forward_runs_each_command_once(self) -> None:
        history = History("brainfuck", "++++[>++<-]>.", "")
        for step in range(10):
            history.at(step)
        for step in reversed(range(10)):
            history.at(step)
        # ``top`` only moves when the machine is actually stepped, so this
        # is the count of commands executed for twenty lookups.
        assert history.top == 9

    def test_going_back_within_the_window_does_not_replay(self) -> None:
        history = History("brainfuck", "++++[>++<-]>.", "")
        history.at(8)
        with patch("esolangs.tui.replay") as derived:
            for step in reversed(range(9)):
                history.at(step)
            derived.assert_not_called()

    def test_revisiting_a_step_does_not_run_the_machine_again(self) -> None:
        history = History("brainfuck", "++++[>++<-]>.", "")
        history.at(6)
        before = history.top
        for _ in range(5):
            history.at(3)
            history.at(6)
        assert history.top == before

    def test_a_step_older_than_the_window_still_gives_the_right_frame(self) -> None:
        history = History("brainfuck", "++++[>++<-]>.", "")
        history.budget = 1  # forces a trim on the very next frame kept
        history.at(9)
        # The oldest frames are gone, but the answer has to be identical.
        assert history.at(0) == replay("brainfuck", "++++[>++<-]>.", "", 0)
        assert history.at(1) == replay("brainfuck", "++++[>++<-]>.", "", 1)

    def test_the_retained_window_is_bounded(self) -> None:
        history = History("brainfuck", "+" * 200, "")
        history.budget = 1
        history.at(150)
        # Without a bound this would hold every step; the trim keeps it to a
        # small tail, which is what stops a long run exhausting memory.
        assert history.retained < 20

    def test_a_fault_matches_what_replay_reports(self) -> None:
        history = History("brainfuck", ",.", "")
        frame = history.at(5)
        assert frame == replay("brainfuck", ",.", "", 5)
        assert frame.fault is not None

    def test_past_the_halt_reports_the_step_really_reached(self) -> None:
        history = History("brainfuck", "++", "")
        frame = history.at(1_000)
        assert frame.halted
        assert frame.step == 2

    def test_a_negative_step_is_the_start(self) -> None:
        assert History("brainfuck", "+++", "").at(-5).step == 0

    def test_an_unknown_language_raises_on_construction(self) -> None:
        with pytest.raises(ValueError, match="unknown language"):
            History("Nonesuch", "+", "")


class _Keys:
    """A scripted keyboard, and the screens the loop painted into it."""

    def __init__(self, keys: str) -> None:
        self.pending = list(keys)
        self.screens: list[str] = []

    def read(self) -> str:
        # Running out of keys ends the loop, which is what a closed stream
        # does too -- otherwise a test that forgets to quit would hang.
        return self.pending.pop(0) if self.pending else ""

    def write(self, text: str) -> None:
        self.screens.extend(s for s in text.split(CLEAR) if s.strip())

    def headers(self) -> list[str]:
        return [s.splitlines()[0] for s in self.screens]


def _drive(program: str, keys: str, **kwargs: object) -> _Keys:
    keyboard = _Keys(keys)
    drive(
        History("brainfuck", program, ""),
        keyboard.read,
        keyboard.write,
        **kwargs,  # type: ignore[arg-type]
    )
    return keyboard


class TestDrive:
    """The key loop, run in process over a scripted keyboard."""

    def test_it_paints_before_reading_the_first_key(self) -> None:
        keyboard = _drive("+++", "q")
        assert len(keyboard.screens) == 1
        assert "step 0" in keyboard.headers()[0]

    def test_space_advances_one_step(self) -> None:
        assert "step 2" in _drive("+++", "  q").headers()[-1]

    @pytest.mark.parametrize("key", [" ", "\r", "\n"])
    def test_every_step_key_advances(self, key: str) -> None:
        assert "step 1" in _drive("+++", key + "q").headers()[-1]

    def test_back_returns_to_the_previous_step(self) -> None:
        assert "step 1" in _drive("+++", "  bq").headers()[-1]

    def test_back_at_the_start_stays_at_the_start(self) -> None:
        assert "step 0" in _drive("+++", "bbbq").headers()[-1]

    def test_run_goes_to_the_halt(self) -> None:
        header = _drive("+++", "rq").headers()[-1]
        assert "step 3" in header
        assert "halted" in header

    def test_back_after_run_lands_on_the_last_real_step(self) -> None:
        # The run key asks for its whole bound, so this is the regression
        # guard for reporting a step the program never reached.
        assert "step 2" in _drive("+++", "rbq").headers()[-1]

    def test_an_unknown_key_repaints_without_moving(self) -> None:
        keyboard = _drive("+++", "zq")
        assert all("step 0" in head for head in keyboard.headers())

    @pytest.mark.parametrize("key", ["q", "\x03"])
    def test_quit_keys_stop_the_loop(self, key: str) -> None:
        assert len(_drive("+++", key + "   ").screens) == 1

    def test_running_out_of_input_stops_the_loop(self) -> None:
        # No quit key at all; the loop has to end rather than spin.
        assert len(_drive("+++", " ").screens) == 2

    def test_it_paints_at_the_size_it_is_given(self) -> None:
        keyboard = _drive("+" * 400, "q", get_size=lambda: (12, 40))
        painted = _plain(keyboard.screens[0]).replace("\r", "").splitlines()
        assert len(painted) <= 12
        assert all(len(line) <= 40 for line in painted)

    def test_the_run_bound_is_respected(self) -> None:
        # An endless program must stop at the bound rather than run away.
        header = _drive("+[]", "rq", max_steps=50).headers()[-1]
        assert "step 50" in header
        assert "halted" not in header


class TestBreakpoints:
    """The conditions the debugger already had, reachable from the screen."""

    def test_no_breakpoint_asked_for_is_no_predicate(self) -> None:
        assert breakpoint_for() is None

    def test_it_stops_on_a_cell_value(self) -> None:
        history = History("brainfuck", "+++++", "")
        frame = history.find(0, breakpoint_for(cell=(0, 3)), 100)
        assert frame.memory == (3,)

    def test_it_stops_on_an_ip(self) -> None:
        history = History("brainfuck", "+++++", "")
        assert history.find(0, breakpoint_for(at=2), 100).ip == 2

    def test_it_stops_on_output(self) -> None:
        history = History("brainfuck", "++++++++[>++++++++<-]>+.+.+.", "")
        frame = history.find(0, breakpoint_for(output="A"), 10_000)
        assert frame.output == "A"

    def test_several_stop_at_whichever_comes_first(self) -> None:
        history = History("brainfuck", "+++++", "")
        stop = breakpoint_for(at=4, cell=(0, 2))
        assert history.find(0, stop, 100).step == 2

    def test_a_condition_never_met_runs_to_the_halt(self) -> None:
        history = History("brainfuck", "+++", "")
        frame = history.find(0, breakpoint_for(cell=(0, 99)), 100)
        assert frame.halted

    def test_a_cell_beyond_the_tape_never_fires(self) -> None:
        history = History("brainfuck", "+++", "")
        assert history.find(0, breakpoint_for(cell=(9, 1)), 100).halted

    def test_without_a_predicate_it_runs_to_the_halt(self) -> None:
        assert History("brainfuck", "+++", "").find(0, None, 100).step == 3

    def test_it_searches_forward_from_where_it_is_told(self) -> None:
        # The same cell value is passed twice; continuing from after the
        # first has to find the second rather than stopping where it is.
        history = History("brainfuck", "+>+<+", "")
        stop = breakpoint_for(cell=(0, 1))
        first = history.find(0, stop, 100)
        assert first.step == 1
        assert history.find(first.step, stop, 100).step > first.step

    def test_the_limit_bounds_a_condition_that_never_fires(self) -> None:
        history = History("brainfuck", "+[]", "")
        assert history.find(0, breakpoint_for(at=99), 40).step == 40

    def test_it_agrees_with_the_debugger_it_mirrors(self) -> None:
        # The screen's breakpoints are predicates over kept frames while the
        # command line's run a live machine; both must stop in the same
        # place, or `--break-on-output` would mean two things.
        program = "++++++++[>++++++++<-]>+.+."
        dbg = esolangs.make_debugger("brainfuck", program)
        dbg.break_on_output("A")
        dbg.run()
        frame = History("brainfuck", program, "").find(
            0, breakpoint_for(output="A"), 10_000
        )
        assert frame.output == dbg.output
        assert frame.ip == dbg.ip
        assert frame.memory == tuple(dbg.memory)


class TestContinueKey:
    def test_c_stops_at_the_breakpoint(self) -> None:
        keyboard = _Keys("cq")
        drive(
            History("brainfuck", "+++++", ""),
            keyboard.read,
            keyboard.write,
            stop=breakpoint_for(cell=(0, 3)),
        )
        assert "step 3" in keyboard.headers()[-1]

    def test_c_without_a_breakpoint_runs_to_the_halt(self) -> None:
        # Continue means "to the next breakpoint, or the halt", so with none
        # set it is the run key rather than a key that does nothing.
        assert "halted" in _drive("+++", "cq").headers()[-1]

    def test_c_continues_past_a_breakpoint_already_reached(self) -> None:
        keyboard = _Keys("ccq")
        drive(
            History("brainfuck", "+>+<+", ""),
            keyboard.read,
            keyboard.write,
            stop=breakpoint_for(cell=(0, 1)),
        )
        headers = keyboard.headers()
        assert "step 1" in headers[1]
        assert "step 1" not in headers[2]

    def test_the_footer_offers_the_key(self) -> None:
        assert "c continue" in render(_frame("+", 0))


class TestBreakpointMarks:
    """A place the run will stop, told apart from the place it is now."""

    def test_a_breakpoint_is_painted_in_its_own_colour(self) -> None:
        screen = render(_frame("+>-<", 0), breaks=(Mark(0, 2),))
        assert _marked_break(screen) == ["-"]
        # And the cursor keeps its own marking, elsewhere.
        assert _highlighted(screen) == "+"

    def test_a_breakpoint_under_the_cursor_shows_as_both(self) -> None:
        # Neither may hide the other: stepping onto a breakpoint must not
        # make it look like the breakpoint is gone.
        screen = render(_frame("+>-<", 2), breaks=(Mark(0, 2),))
        assert _marked_both(screen) == ["-"]
        assert _highlighted(screen) is None
        assert _marked_break(screen) == []

    def test_every_combination_of_states_looks_different(self) -> None:
        # Red and reverse-video-red are two shades of the same thing, so the
        # states carry shape cues as well: bold where the run meets a
        # breakpoint, an underline for the selector.  A reader who cannot
        # separate the colours still has a cue, and so does an odd palette.
        seen = [
            _sgr(render(_frame("+>-<", 2))),
            _sgr(render(_frame("+>-<", 0), breaks=(Mark(0, 2),))),
            _sgr(render(_frame("+>-<", 2), breaks=(Mark(0, 2),))),
            _sgr(render(_frame("+>-<", 0), picked=Mark(0, 2))),
            _sgr(render(_frame("+>-<", 0), breaks=(Mark(0, 2),), picked=Mark(0, 2))),
        ]
        assert len(set(seen)) == len(seen), seen

    def test_several_breakpoints_on_one_row_are_all_painted(self) -> None:
        screen = render(_frame("abcdef", 0), breaks=(Mark(0, 2), Mark(0, 4)))
        assert _marked_break(screen) == ["c", "e"]

    def test_breakpoints_on_different_rows_are_all_painted(self) -> None:
        screen = render(_frame("ab\ncd", 0), breaks=(Mark(0, 1), Mark(1, 1)))
        assert _marked_break(screen) == ["b", "d"]

    def test_a_position_that_does_not_locate_is_not_painted(self) -> None:
        # A breakpoint past the end of the program has nowhere to go, and
        # must not be drawn at some other character instead.
        assert _marked_break(render(_frame("abc", 0), breaks=(Mark(9, 0),))) == []

    def test_a_grid_breakpoint_is_painted_at_its_cell(self) -> None:
        frame = _frame("abc\ndef", (0, 0), language="Streetcode", ip_shape="grid")
        assert _marked_break(render(frame, breaks=(Mark(1, 2),))) == ["f"]

    def test_the_header_counts_them(self) -> None:
        assert "2 breaks" in render(
            _frame("abcdef", 0), breaks=(Mark(0, 2), Mark(0, 4))
        )
        assert "1 break" in render(_frame("abcdef", 0), breaks=(Mark(0, 2),))

    def test_no_count_when_there_are_none(self) -> None:
        assert "break" not in render(_frame("abc", 0)).splitlines()[0]

    def test_the_footer_offers_the_toggle(self) -> None:
        assert "t break" in render(_frame("+", 0))

    def test_a_breakpoint_scrolled_out_of_view_is_not_painted(self) -> None:
        program = "." * 400 + "@" + "." * 400
        screen = render(_frame(program, 800), width=60, breaks=(Mark(0, 0),))
        assert _marked_break(screen) == []


class TestToggleKey:
    def test_t_marks_the_position_the_run_is_on(self) -> None:
        keyboard = _drive("+++", " tq")
        assert _marked_both(keyboard.screens[-1]) == ["+"]
        assert "1 break" in keyboard.headers()[-1]

    def test_t_again_clears_it(self) -> None:
        keyboard = _drive("+++", "ttq")
        assert "break" not in keyboard.headers()[-1]

    def test_a_toggled_breakpoint_stops_a_continue(self) -> None:
        # Step to 1, mark it, run to the halt, then continue: the run comes
        # back round to the marked position rather than stopping only at the
        # end.
        keyboard = _drive("+>+<+", " tbcq")
        assert "step 1" in keyboard.headers()[-1]

    def test_continue_does_not_stop_where_it_already_is(self) -> None:
        # Marking the current position and continuing has to move, or the
        # key would appear dead.
        keyboard = _drive("+++", "tcq")
        assert "step 0" not in keyboard.headers()[-1]

    def test_toggling_does_not_move_the_run(self) -> None:
        before = _drive("+++", " q").headers()[-1]
        after = _drive("+++", " tq").headers()[-1]
        assert "step 1" in before
        assert "step 1" in after

    def test_a_language_with_no_position_cannot_be_marked(self) -> None:
        keyboard = _Keys("tq")
        drive(History("Circuit Diagram", "-.\n", ""), keyboard.read, keyboard.write)
        assert "break" not in keyboard.headers()[-1]

    def test_a_position_given_on_the_command_line_starts_marked(self) -> None:
        keyboard = _Keys("q")
        drive(History("brainfuck", "+>-<", ""), keyboard.read, keyboard.write, at=(2,))
        assert _marked_break(keyboard.screens[0]) == ["-"]

    def test_a_command_line_position_also_stops_a_continue(self) -> None:
        keyboard = _Keys("cq")
        drive(History("brainfuck", "+>-<", ""), keyboard.read, keyboard.write, at=(2,))
        assert "step 2" in keyboard.headers()[-1]


class TestAtCell:
    """Turning a place on the screen into the mark a position there makes."""

    def test_a_cell_is_itself(self) -> None:
        assert at_cell("abc\ndef", "offset", 1, 2) == Mark(1, 2)
        assert at_cell("abc\ndef", "grid", 1, 2) == Mark(1, 2)

    def test_a_line_language_takes_the_whole_line(self) -> None:
        # A line counter cannot tell one column from another, so a
        # breakpoint anywhere on the row means the row.
        assert at_cell("ab\ncdef", "line", 1, 3) == Mark(1, 0, 4)
        assert at_cell("ab\ncdef", "line", 1, 0) == at_cell("ab\ncdef", "line", 1, 3)

    def test_a_language_with_no_source_position_holds_none(self) -> None:
        assert at_cell("abc", "opaque", 0, 1) is None

    def test_outside_the_rectangle_is_nothing(self) -> None:
        assert at_cell("abc", "offset", 9, 0) is None
        assert at_cell("abc", "offset", 0, 9) is None

    def test_it_agrees_with_locate(self) -> None:
        # The two have to meet, or a breakpoint set by hand would never be
        # recognised when the run arrived at it.
        program = "abc\ndef"
        assert at_cell(program, "offset", 1, 1) == locate(program, 5)
        assert at_cell(program, "grid", 1, 1) == locate(program, (1, 1, 3), "grid")
        assert at_cell(program, "line", 1, 2) == locate(program, (1,), "line")


class TestSelector:
    """A selector that can reach where the run has not."""

    def test_it_starts_on_the_running_position(self) -> None:
        assert _selected(_drive("+++", "q").screens[0]) == ["+"]

    @pytest.mark.parametrize(
        ("keys", "expected"),
        [
            ("", "+"),  # starts on the run
            ("l", ">"),
            ("j", "<"),
            ("lj", "-"),
            ("h", "+"),  # already at the left edge
            ("k", "+"),  # already at the top
            ("ljhk", "+"),  # there and back
        ],
    )
    def test_the_movement_keys_move_it(self, keys: str, expected: str) -> None:
        # Four distinct commands on a two-by-two rectangle, so every
        # direction lands somewhere it can be told apart from the others.
        keyboard = _drive("+>\n<-", keys + "q")
        assert _selected(keyboard.screens[-1]) == [expected]

    def test_moving_does_not_move_the_run(self) -> None:
        assert "step 0" in _drive("+++", "lllq").headers()[-1]

    def test_it_stops_at_the_edges(self) -> None:
        # Walking off the rectangle would either crash or wrap; it holds.
        keyboard = _drive("+++", "hhhhkkkkq")
        assert _selected(keyboard.screens[-1]) == ["+"]

    def test_stepping_snaps_it_back_to_the_run(self) -> None:
        # Otherwise "where am I" and "where am I pointing" drift apart.
        keyboard = _drive("+>-<", "ll q")
        assert _selected(keyboard.screens[-1]) == [">"]

    def test_a_breakpoint_can_be_set_where_the_run_has_not_reached(self) -> None:
        # The whole point: mark the third command while standing on the
        # first, then continue to it.
        keyboard = _drive("+>-<", "lltcq")
        assert "step 2" in keyboard.headers()[-1]

    def test_marking_ahead_paints_there_not_here(self) -> None:
        keyboard = _drive("+>-<", "lltq")
        assert _marked_break(keyboard.screens[-1]) == ["-"]
        assert _highlighted(keyboard.screens[-1]) == "+"

    def test_the_pane_follows_the_selector(self) -> None:
        # A selector that can leave the window is a selector you lose.
        program = "." * 400 + "@" + "." * 400
        screen = render(_frame(program, 0), width=60, picked=Mark(0, 400))
        assert _selected(screen) == ["@"]

    def test_a_language_with_no_position_has_no_selector(self) -> None:
        keyboard = _Keys("llq")
        drive(History("Circuit Diagram", "-.\n", ""), keyboard.read, keyboard.write)
        assert _selected(keyboard.screens[-1]) == []

    def test_the_footer_offers_the_keys(self) -> None:
        assert "hjkl move" in render(_frame("+", 0))


class TestBoundaries:
    """The off-by-ones, each pinned at the exact edge it turns on.

    A mutation sweep over this module found the tests below missing: every
    bound here was asserted somewhere far outside it -- a row 5 past a
    2-row program -- which a widened comparison passes just as happily.
    The edge is the only place the two readings differ.
    """

    def test_a_grid_row_one_past_the_last_is_outside(self) -> None:
        assert locate("ab\ncd", (2, 0), "grid") is None

    def test_a_grid_column_one_past_the_width_is_outside(self) -> None:
        assert locate("ab\ncd", (0, 2), "grid") is None

    def test_a_line_one_past_the_last_is_outside(self) -> None:
        assert locate("ab\ncd", (2,), "line") is None

    def test_an_offset_one_past_the_text_is_outside(self) -> None:
        # The halt boundary lands here, so this is the common case rather
        # than an exotic one.
        assert locate("abc", 3) is None
        assert locate("abc", 2) == Mark(0, 2)

    def test_a_cell_one_past_the_width_holds_nothing(self) -> None:
        assert at_cell("abc", "offset", 0, 3) is None
        assert at_cell("abc", "offset", 0, 2) == Mark(0, 2)

    def test_the_program_pane_is_filled_when_there_is_enough_program(self) -> None:
        # Scrolling that runs past the end leaves the pane short rather than
        # showing the focus somewhere wrong, so the symptom is a half-empty
        # screen at the bottom of a long program.
        program = "\n".join(f"L{i}" for i in range(100))
        tall = render(_frame(program, program.index("L99")), height=24)
        short = render(_frame(program, 0), height=24)
        body = [line for line in _plain(short).splitlines() if "|" in line]
        assert len([ln for ln in _plain(tall).splitlines() if "|" in ln]) == len(body)

    def test_a_value_that_exactly_fits_is_kept(self) -> None:
        # ``1 2 3`` is six characters of budget for five of text; at exactly
        # six nothing has to be dropped.
        assert _cells((1, 2, 3), 6) == "1 2 3"

    def test_the_dropped_count_may_fill_the_budget_exactly(self) -> None:
        # Ten values and " +9 more" come to precisely thirty; a stricter
        # test would give up a value it did not need to.
        row = _cells(tuple(range(20)), 30)
        assert len(row) == 30
        assert row.endswith("+9 more")

    def test_a_mark_wider_than_the_window_is_cut_to_it(self) -> None:
        # A line-shape mark spans a whole row, which can be wider than the
        # pane; padding it to its full span would overrun the screen.
        frame = _frame("abcdefghij", (0,), ip_shape="line")
        screen = render(frame, width=10)
        assert all(len(line) <= 10 for line in _plain(screen).splitlines())

    def test_a_mark_just_past_the_window_is_not_painted_at_all(self) -> None:
        # One column past the right edge must be skipped, not painted as an
        # empty run -- which is what a widened bound produces.
        screen = render(_frame("." * 200, 0), width=60, breaks=(Mark(0, 56),))
        assert _marked_break(screen) == []

    def test_the_run_on_a_breakpoint_is_more_than_a_colour(self) -> None:
        # Bold is what makes it differ from the breakpoint alone to look at:
        # reverse video puts the red on the foreground, so the two are the
        # same hue and only a shape separates them.
        (code,) = [
            c
            for c, _ in _STYLED.findall(render(_frame("+>-<", 2), breaks=(Mark(0, 2),)))
        ]
        assert {"1", "4"} & set(code.split(";")), code

    def test_the_limit_is_not_overrun_by_one(self) -> None:
        # A breakpoint one step past the bound must not be reported: the
        # bound is what stops an endless program dead.
        history = History("brainfuck", "+" * 10, "")
        frame = history.find(0, breakpoint_for(cell=(0, 6)), 5)
        assert frame.step == 5

    def test_a_marked_position_and_a_condition_stop_at_either(self) -> None:
        # The two sources of breakpoint are alternatives, not a conjunction;
        # requiring both would make each one silently inert.
        keyboard = _Keys("cq")
        drive(
            History("brainfuck", "+++", ""),
            keyboard.read,
            keyboard.write,
            stop=breakpoint_for(cell=(0, 3)),
            at=(1,),
        )
        assert "step 1" in keyboard.headers()[-1]


class TestWatch:
    """One cell's value over time, read off the frames already kept."""

    def test_it_traces_a_cell_step_by_step(self) -> None:
        history = History("brainfuck", "+++", "")
        history.at(3)
        assert history.trace(0, 3, 10) == (0, 1, 2, 3)

    def test_it_reaches_back_only_as_far_as_asked(self) -> None:
        history = History("brainfuck", "+++", "")
        history.at(3)
        assert history.trace(0, 3, 2) == (2, 3)

    def test_it_ends_where_the_run_is_standing(self) -> None:
        # Stepping back shortens the trace, because it is a view over the
        # run rather than a log that only grows.
        history = History("brainfuck", "+++", "")
        history.at(3)
        assert history.trace(0, 1, 10) == (0, 1)

    def test_a_cell_the_tape_has_not_reached_reads_as_absent(self) -> None:
        history = History("brainfuck", "+++", "")
        history.at(3)
        assert history.trace(9, 3, 10) == (None,) * 4

    def test_it_stops_at_the_retained_window(self) -> None:
        # The budget bounds what is kept, so it bounds the trace too; the
        # answer is short rather than wrong.
        history = History("brainfuck", "+" * 100, "")
        history.budget = 1
        history.at(100)
        assert 0 < len(history.trace(0, 100, 256)) < 30

    def test_an_empty_history_traces_nothing(self) -> None:
        history = History("brainfuck", "+", "")
        assert history.trace(0, 0, 10) == (0,)

    def test_the_row_shows_the_values(self) -> None:
        screen = render(_frame("+", 0), watch=(0, (0, 1, 2, 3)))
        assert "cell 0: 0 1 2 3" in screen

    def test_no_row_when_nothing_is_watched(self) -> None:
        assert "watch" not in render(_frame("+", 0))

    def test_an_absent_value_is_shown_as_a_dash(self) -> None:
        assert "- - 1" in render(_frame("+", 0), watch=(0, (None, None, 1)))

    def test_the_newest_values_survive_a_narrow_row(self) -> None:
        # A tape is read from cell zero outwards, but a trace is read from
        # now backwards, so the *end* is what must not be dropped.
        screen = render(_frame("+", 0), watch=(0, tuple(range(100))), width=40)
        assert "99" in screen
        assert all(len(line) <= 40 for line in _plain(screen).splitlines())

    def test_a_trimmed_trace_says_so(self) -> None:
        screen = render(_frame("+", 0), watch=(0, tuple(range(100))), width=40)
        assert "..." in screen

    def test_an_empty_trace_says_so_rather_than_showing_nothing(self) -> None:
        assert "(none yet)" in render(_frame("+", 0), watch=(0, ()))

    def test_the_row_costs_the_program_pane_one_line(self) -> None:
        program = "\n".join("x" for _ in range(40))
        without = render(_frame(program, 0), height=20)
        with_watch = render(_frame(program, 0), height=20, watch=(0, (1, 2)))
        assert len(with_watch.splitlines()) == len(without.splitlines())

    def test_the_loop_shows_the_trace_growing(self) -> None:
        keyboard = _Keys("   q")
        drive(History("brainfuck", "+++", ""), keyboard.read, keyboard.write, watch=0)
        assert "cell 0: 0" in keyboard.screens[0]
        assert "cell 0: 0 1 2 3" in keyboard.screens[-1]

    def test_stepping_back_shortens_it(self) -> None:
        keyboard = _Keys("   bq")
        drive(History("brainfuck", "+++", ""), keyboard.read, keyboard.write, watch=0)
        assert "cell 0: 0 1 2" in keyboard.screens[-1]
        assert "cell 0: 0 1 2 3" not in keyboard.screens[-1]


class TestRawTerminal:
    """``run_tui`` itself, driven through a pty.

    This is the part :func:`drive` cannot cover: putting a real terminal in
    raw mode, reading from it, and restoring it afterwards.  One program,
    a few keys, and a hard deadline -- a loop that never returns has to fail
    here rather than hang the suite.
    """

    @pytest.mark.skipif(sys.platform == "win32", reason="no pty on Windows")
    def test_it_paints_and_quits_on_a_real_terminal(self) -> None:
        import contextlib
        import os
        import pty
        import select
        import signal
        import time

        source = (
            "from esolangs.tui import run_tui\nrun_tui('brainfuck', '+++>++.', '')\n"
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
                ready, _, _ = select.select([fd], [], [], 0.2)
                if not ready:
                    continue
                try:
                    chunk = os.read(fd, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                out += chunk.decode("utf-8", "replace")
                quiet = time.time() + 0.4
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
    """That the highlighted character is the op the VM is about to run.

    The screen's whole claim is this correspondence, and it is the one thing
    a pure-function test cannot assert by itself -- it needs the interpreter
    to say where it is.
    """

    @pytest.mark.parametrize("step", range(12))
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
