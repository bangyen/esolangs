"""Streetcode through the shared API, CLI and machinery."""

from pathlib import Path

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.tui import Mark, render
from tests.cli_support import call_both
from tests.generator_support import evaluate_generated, overruns
from tests.samples import STREETCODE, STREETCODE_GAP
from tests.test_tui import _frame, _highlighted, _marked_both, _marked_break, _sgr
from tests.test_validation import _debugger
from tests.test_vm import _run_all
from tests.test_vm_protocol import assert_starts_downward


class TestBreakpointMarks:
    """A place the run will stop, told apart from the place it is now."""

    def test_a_breakpoint_is_painted_in_its_own_colour(self) -> None:
        screen = render(_frame("+>-<", 0), breaks=(Mark(0, 2),))
        assert _marked_break(screen) == ["-"]
        assert _highlighted(screen) == "+"

    def test_a_breakpoint_under_the_cursor_shows_as_both(self) -> None:
        screen = render(_frame("+>-<", 2), breaks=(Mark(0, 2),))
        assert _marked_both(screen) == ["-"]
        assert _highlighted(screen) is None
        assert _marked_break(screen) == []

    def test_every_combination_of_states_looks_different(self) -> None:
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

    def test_a_breakpoint_scrolled_out_of_view_is_not_painted(self) -> None:
        program = "." * 400 + "@" + "." * 400
        screen = render(_frame(program, 800), width=60, breaks=(Mark(0, 0),))
        assert _marked_break(screen) == []


class TestABreakpointMustBeAbleToFire:
    """A breakpoint that can never match is worse than a refused one."""

    @pytest.mark.parametrize("ip", ["x", 1.5, None])
    def test_a_non_position_is_refused(self, ip: object) -> None:
        with pytest.raises(esolangs.ArgumentError, match="ip must be"):
            _debugger().break_at(ip)  # type: ignore[arg-type]

    def test_a_grid_coordinate_is_still_accepted(self) -> None:
        """A 2D language's ``ip`` is a tuple, so that spelling must pass."""
        program = esolangs.generate("Streetcode", "0110")
        dbg = debugger_api.make_debugger(
            "Streetcode", program, stdin=esolangs.encode_inputs("Streetcode", [0, 1])
        )
        assert isinstance(dbg.ip, tuple)
        dbg.break_at(dbg.ip)
        assert dbg.run(max_steps=5) == "breakpoint"

    def test_a_non_integer_cell_value_is_refused(self) -> None:
        with pytest.raises(esolangs.ArgumentError, match="value must be"):
            _debugger().break_on_cell(0, "x")  # type: ignore[arg-type]

    @pytest.mark.parametrize("index", [-5, "x"])
    def test_a_bad_watch_index_is_refused(self, index: object) -> None:
        """``watch_cell(-5)`` raised a bare IndexError from a later run."""
        with pytest.raises(esolangs.ArgumentError, match="index"):
            _debugger().watch_cell(index)  # type: ignore[arg-type]


class TestStreetcode:
    def test_car_position_heading_and_cells(self) -> None:
        vm = debugger_api.make_vm("Streetcode", STREETCODE)
        assert vm.ip == (2, 1, 1)  # on the C, heading east
        assert vm.memory == []
        vm.step()  # drives onto the first ^
        assert vm.ip == (2, 2, 1)
        vm.step()  # ^ increments the cell under CP
        assert vm.memory == [1]
        vm.step()  # ^ again
        assert vm.memory == [2]
        vm.step()  # O prints it
        assert vm.output == "\x02"
        assert vm.stack == []

    def test_memory_fills_the_gaps_between_written_cells(self) -> None:
        """The tape is a sparse dict, so a skipped cell still reads as zero."""
        vm = debugger_api.make_vm("Streetcode", STREETCODE_GAP)
        assert _run_all(vm) == ""
        assert vm.memory == [1, 0, 1]


class TestTheAdvisoryNotesAreRenderedOnce:
    """The library warns; this command renders, and does not also duplicate."""

    def test_a_surplus_line_is_noted_without_pythons_framing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A raw UserWarning would print this file's path and a line of it."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "00010111"))
        out, err = call_both(["run", "brainfuck", str(path)], capsys, stdin="110011")
        assert out == "1"
        assert "read 3 of the 6 lines" not in err
        assert "UserWarning" not in err
        assert "cli.py" not in err

    def test_an_empty_program_file_is_noted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It ran and printed nothing, at exit 0, with no explanation."""
        path = tmp_path / "empty.txt"
        path.write_text("")
        _out, err = call_both(["run", "brainfuck", str(path)], capsys, stdin="0\n0\n")
        assert "is empty" in err

    def test_a_mixed_none_watch_history_is_legended(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The all-None case was annotated; the mixed one needed it more."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("Streetcode", "0110"))
        out, _err = call_both(
            ["debug", "--steps", "30", "--watch-cell", "0", "Streetcode", str(path)],
            capsys,
            stdin="0\n1\n",
        )
        assert "did not exist yet" in out


def test_width_floor_matches_its_source_and_overrun_count() -> None:
    """Warnings follow actual rendered widths, including narrower constructions."""
    assert esolangs.describe("Streetcode")["width_aware"]
    source = esolangs.generate("Streetcode", "10010110", width=1)
    assert max(map(len, source.splitlines())) == 7
    assert overruns("Streetcode", "10010110") == (2, 6)
    assert evaluate_generated("Streetcode", "10010110", width=1) == "10010110"


def test_the_first_move_is_down_the_rows() -> None:
    """It begins vertically, so ``VM.ip``'s first component moves first."""
    assert_starts_downward("Streetcode")
