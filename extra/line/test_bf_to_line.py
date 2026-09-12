r"""Tests for bf_to_line.py, driven through the *real* render pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest
import render as render_module
from bf_to_line import bf_to_line
from extract import extract
from render import render
from simulate import IO, run


def _run_bf(program: str, path: Path, inputs: list[int] | None = None) -> list[int]:
    r"""Compile, draw, re-extract and execute ``program``, returning its."""
    outputs: list[int] = []
    values = iter(inputs or [])
    render(bf_to_line(program)).save(str(path))
    run(extract(str(path)), IO(read=lambda: next(values), write=outputs.append))
    return outputs


class TestStraightLine:
    r"""Loop-free programs: the baseline that never depended on loop."""

    def test_increment_and_print(self, tmp_path: Path) -> None:
        r"""Three `+` then `.` prints 3."""
        assert _run_bf("+++.", tmp_path / "inc.png") == [3]

    def test_pointer_movement(self, tmp_path: Path) -> None:
        r"""`>` moves the pointer, so `.` prints the second cell."""
        assert _run_bf("+>++.", tmp_path / "move.png") == [2]

    def test_input_is_echoed(self, tmp_path: Path) -> None:
        r"""`,` reads a whole number and `.` prints it back unchanged."""
        assert _run_bf(",.", tmp_path / "echo.png", inputs=[7]) == [7]


class TestSingleLoop:
    r"""One level of `[...]`, drawn as a real reconnecting stroke."""

    def test_clear_loop_zeroes_cell(self, tmp_path: Path) -> None:
        r"""`[-]` decrements until the cell reads zero, then falls through."""
        assert _run_bf("+++[-].", tmp_path / "clear.png") == [0]

    def test_move_loop_transfers_cell(self, tmp_path: Path) -> None:
        r"""`[>+<-]` moves a cell's value one place right."""
        assert _run_bf("+++[>+<-]>.", tmp_path / "move_loop.png") == [3]

    def test_multiply_loop(self, tmp_path: Path) -> None:
        r"""The classic 8x8 multiply loop, plus one, reaches 65."""
        assert _run_bf("++++++++[>++++++++<-]>+.", tmp_path / "mul.png") == [65]

    def test_loop_body_never_runs_on_zero_cell(self, tmp_path: Path) -> None:
        r"""A loop whose cell is already 0 falls straight through to its exit."""
        assert _run_bf("[>+<-]>.", tmp_path / "skip.png") == [0]


class TestNestedLoops:
    r"""Two levels of real `[...]` -- the case WIP.md recorded as broken."""

    def test_nested_multiply_prints_result(self, tmp_path: Path) -> None:
        r"""The exact program WIP.md recorded as silently truncating."""
        assert _run_bf("++[>++[>+<-]<-]>>.", tmp_path / "nested.png") == [4]

    def test_nested_loop_reaches_code_after_outer_loop(self, tmp_path: Path) -> None:
        r"""The op *after* a nested loop still runs -- the exact truncation."""
        assert _run_bf("++[>++[>+<-]<-]>>+++.", tmp_path / "nested_tail.png") == [7]


def _max_between_stroke_adjacency(program: str) -> int:
    r"""Most cells of one stroke sitting flush against a *different* stroke."""
    captured: list[list[tuple[int, int]]] = []
    original = render_module._Cursor.finish  # noqa: SLF001 - see docstring

    def spy(self) -> None:  # type: ignore[no-untyped-def]
        before = len(self.strokes)
        original(self)
        # Only real drawing cursors,.
        # ones: measuring lays every.
        # in its own local frame, so.
        # space unrelated to the.
        # The shared `occupied` set is.
        # the real render (scratch.
        if self.occupied is not None:
            captured.extend(self.strokes[before:])

    render_module._Cursor.finish = spy  # noqa: SLF001 - deliberate stroke spy
    try:
        render(bf_to_line(program))
    finally:
        render_module._Cursor.finish = original  # noqa: SLF001 - restore the spy

    worst = 0
    for i, first in enumerate(captured):
        for second in captured[i + 1 :]:
            a, b = set(first), set(second)
            if a & b:
                continue
            adjacent = sum(
                1
                for (y, x) in a
                if any((y + dy, x + dx) in b for dy in (-1, 0, 1) for dx in (-1, 0, 1))
            )
            worst = max(worst, adjacent)
    return worst


class TestStrokeSeparation:
    r"""Unrelated strokes must never be drawn flush against each other."""

    @pytest.mark.parametrize(
        "program",
        [
            "+++[-].",
            "+[>+<-]>.",
            "++[>++[>+<-]<-]>>.",
            "++[>++[>+<-]<-]>>+++.",
            "+[-]+[-]+[-].",
            "++[>+<-]>[>+<-]>.",
        ],
    )
    def test_no_two_strokes_run_flush(self, program: str) -> None:
        r"""No stroke touches a different stroke it does not share a cell with."""
        assert _max_between_stroke_adjacency(program) == 0


class TestNestingDepth:
    r"""Nesting depth is unbounded: loop-backs are constructed, not routed."""

    def test_three_levels_round_trip(self, tmp_path: Path) -> None:
        r"""Depth 3 renders, extracts and executes correctly."""
        assert _run_bf("+[>+[>+[>+<-]<-]<-]>>>.", tmp_path / "depth3.png") == [1]

    def test_heavy_three_levels_round_trip(self, tmp_path: Path) -> None:
        r"""A depth-3 body heavy enough to have exhausted the old router works."""
        assert _run_bf("++[>++[>++[>+<-]<-]<-]>>>.", tmp_path / "d3heavy.png") == [8]

    def test_four_levels_round_trip(self, tmp_path: Path) -> None:
        r"""Depth 4 renders, extracts and executes correctly."""
        assert _run_bf("+[>+[>+[>+[>+<-]<-]<-]<-]>>>>.", tmp_path / "depth4.png") == [1]

    def test_five_levels_round_trip(self, tmp_path: Path) -> None:
        r"""Depth 5 renders, extracts and executes correctly."""
        assert _run_bf(
            "+[>+[>+[>+[>+[>+<-]<-]<-]<-]<-]>>>>>.", tmp_path / "depth5.png"
        ) == [1]

    @pytest.mark.slow  # 5.2s: the deepest nesting the.
    def test_eight_levels_round_trip(self, tmp_path: Path) -> None:
        r"""Depth 8 renders, extracts and executes correctly."""
        assert _run_bf(
            "+[>+[>+[>+[>+[>+[>+[>+[>+<-]<-]<-]<-]<-]<-]<-]<-]>>>>>>>>.",
            tmp_path / "depth8.png",
        ) == [1]

    def test_unconstructible_loop_back_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        r"""A drawing that cannot complete fails loudly, never misdraws."""
        monkeypatch.setattr(render_module, "_loop_return_legs", lambda *_a: None)
        with pytest.raises(ValueError, match="could not be constructed"):
            _run_bf("+++[-].", tmp_path / "unconstructible.png")


class TestCompileErrors:
    r"""`bf_to_line`'s own documented rejections, no rendering involved."""

    @pytest.mark.parametrize("program", ["[", "+[+", "]", "+]"])
    def test_unbalanced_brackets_rejected(self, program: str) -> None:
        r"""An unmatched bracket in either direction is a compile error."""
        with pytest.raises(ValueError, match="unmatched"):
            bf_to_line(program)

    def test_empty_loop_body_rejected(self) -> None:
        r"""`[]` has no node to carry the loop-back `goto` -- see bf_to_line."""
        with pytest.raises(ValueError, match="empty loop body"):
            bf_to_line("+[]")

    def test_program_with_no_commands_rejected(self) -> None:
        r"""`render` needs at least one node, so an all-comment program fails."""
        with pytest.raises(ValueError, match="no recognized commands"):
            bf_to_line("just a comment")
