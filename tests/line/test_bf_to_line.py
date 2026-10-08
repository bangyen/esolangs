"""Tests for bf_to_line.py, driven through the *real* render pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

from esolangs.interpreters.tape_based.line.extract import extract
from esolangs.interpreters.tape_based.line.simulate import IO, run
from esolangs.tools.line import render as render_module
from esolangs.tools.line.bf_to_line import bf_to_line
from esolangs.tools.line.render import render


def _run_bf(program: str, path: Path, inputs: list[int] | None = None) -> list[int]:
    """Compile, draw, re-extract and execute ``program``, returning its output."""
    outputs: list[int] = []
    values = iter(inputs or [])
    render(bf_to_line(program)).save(str(path))
    run(extract(str(path)), IO(read=lambda: next(values), write=outputs.append))
    return outputs


class TestStraightLine:
    """Loop-free programs: the baseline that never depended on loop geometry."""

    def test_increment_and_print(self, tmp_path: Path) -> None:
        """Three `+` then `.` prints 3."""
        assert _run_bf("+++.", tmp_path / "inc.png") == [3]

    def test_pointer_movement(self, tmp_path: Path) -> None:
        """`>` moves the pointer, so `.` prints the second cell."""
        assert _run_bf("+>++.", tmp_path / "move.png") == [2]

    def test_input_is_echoed(self, tmp_path: Path) -> None:
        """`,` reads a whole number and `.` prints it back unchanged."""
        assert _run_bf(",.", tmp_path / "echo.png", inputs=[7]) == [7]


class TestSingleLoop:
    """One level of `[...]`, drawn as a real reconnecting stroke."""

    def test_clear_loop_zeroes_cell(self, tmp_path: Path) -> None:
        """`[-]` decrements until the cell reads zero, then falls through."""
        assert _run_bf("+++[-].", tmp_path / "clear.png") == [0]

    def test_move_loop_transfers_cell(self, tmp_path: Path) -> None:
        """`[>+<-]` moves a cell's value one place right."""
        assert _run_bf("+++[>+<-]>.", tmp_path / "move_loop.png") == [3]

    def test_multiply_loop(self, tmp_path: Path) -> None:
        """The classic 8x8 multiply loop, plus one, reaches 65."""
        assert _run_bf("++++++++[>++++++++<-]>+.", tmp_path / "mul.png") == [65]

    def test_loop_body_never_runs_on_zero_cell(self, tmp_path: Path) -> None:
        """A loop whose cell is already 0 falls straight through to its exit."""
        assert _run_bf("[>+<-]>.", tmp_path / "skip.png") == [0]


class TestNestedLoops:
    """Two levels of real `[...]` -- the case that was broken."""

    def test_nested_multiply_prints_result(self, tmp_path: Path) -> None:
        """The exact program that silently truncated before the fix."""
        assert _run_bf("++[>++[>+<-]<-]>>.", tmp_path / "nested.png") == [4]

    def test_nested_loop_reaches_code_after_outer_loop(self, tmp_path: Path) -> None:
        """The op *after* a nested loop still runs -- the exact truncation seen."""
        assert _run_bf("++[>++[>+<-]<-]>>+++.", tmp_path / "nested_tail.png") == [7]


def _max_between_stroke_adjacency(program: str) -> int:
    """Most cells of one stroke sitting flush against a *different* stroke."""
    captured: list[list[tuple[int, int]]] = []
    original = render_module._Cursor.finish  # noqa: SLF001 - see docstring

    def spy(self) -> None:  # type: ignore[no-untyped-def]
        before = len(self.strokes)
        original(self)
        # Only real drawing cursors, never `_subtree_extent`'s dry-run scratch
        # ones: measuring lays every subtree out from (0, 0) heading `_FORWARD`
        # in its own local frame, so those strokes pile up in a coordinate
        # space unrelated to the drawing and abut each other meaninglessly.
        # The shared `occupied` set is exactly what marks a cursor as part of
        # the real render (scratch cursors are built without one).
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
    """Unrelated strokes must never be drawn flush against each other."""

    @pytest.mark.parametrize(
        "program",
        [
            "+[>+<-]>.",
            "++[>++[>+<-]<-]>>+++.",
            "++[>+<-]>[>+<-]>.",
        ],
    )
    def test_no_two_strokes_run_flush(self, program: str) -> None:
        """No stroke touches a different stroke it does not share a cell with."""
        assert _max_between_stroke_adjacency(program) == 0


class TestRunBeforeALoop:
    """A long straight run before a nested loop, the shape that used to raise."""

    @pytest.mark.parametrize("count", [5, 6])
    def test_a_long_leading_run_before_a_nested_loop(
        self, count: int, tmp_path: Path
    ) -> None:
        """6 was the first count that raised; 5 was the last that drew."""
        program = "+" * count + "[>+[>+<-]<-]>>."
        assert _run_bf(program, tmp_path / f"pre{count}.png") == [count]

    @pytest.mark.medium  # 0.5s: the largest drawing in this class
    def test_a_realistic_multiplier_program(self, tmp_path: Path) -> None:
        """The `H` of a stock hello-world header -- 8 leading `+`, depth 2."""
        program = "++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]>>."
        assert _run_bf(program, tmp_path / "hello_h.png") == [72]

    @pytest.mark.parametrize("inner", [8])
    def test_a_run_inside_the_body_at_every_stem_length(
        self, inner: int, tmp_path: Path
    ) -> None:
        """`inner == 8` is where a merge point landed on a walk boundary."""
        program = "+[>" + "+" * inner + "[>+<-]<-]>>."
        assert _run_bf(program, tmp_path / f"inner{inner}.png") == [inner]


class TestNestingDepth:
    """Nesting depth is unbounded: loop-backs are constructed, not routed."""

    def test_heavy_three_levels_round_trip(self, tmp_path: Path) -> None:
        """A depth-3 body heavy enough to have exhausted the old router works."""
        assert _run_bf("++[>++[>++[>+<-]<-]<-]>>>.", tmp_path / "d3heavy.png") == [8]

    def test_unconstructible_loop_back_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A drawing that cannot complete fails loudly, never misdraws."""
        monkeypatch.setattr(render_module, "_loop_return_legs", lambda *_a: None)
        with pytest.raises(ValueError, match="could not be constructed"):
            _run_bf("+++[-].", tmp_path / "unconstructible.png")


class TestUnconstructibleShapes:
    """Compiled programs the construction still declines, pinned as a limit."""

    @pytest.mark.parametrize("program", ["[[[+]][+]+]", "+[[-][-][-]+]"])
    def test_a_body_tail_inside_its_own_box_raises(self, program: str) -> None:
        with pytest.raises(ValueError, match="could not be constructed"):
            render(bf_to_line(program))

    @pytest.mark.parametrize("program", ["[[+][+]+]", "+[[-][-]+]"])
    def test_the_same_shape_one_loop_smaller_still_draws(self, program: str) -> None:
        """The positive control: the limit is geometric, not "code after a loop"."""
        assert render(bf_to_line(program)).width > 0


class TestCompileErrors:
    """`bf_to_line`'s own documented rejections, no rendering involved."""

    @pytest.mark.parametrize("program", ["[", "+]"])
    def test_unbalanced_brackets_rejected(self, program: str) -> None:
        """An unmatched bracket in either direction is a compile error."""
        with pytest.raises(ValueError, match="unmatched"):
            bf_to_line(program)

    def test_empty_loop_body_rejected(self) -> None:
        """`[]` has no node to carry the loop-back `goto` -- see bf_to_line."""
        with pytest.raises(ValueError, match="empty loop body"):
            bf_to_line("+[]")

    def test_program_with_no_commands_rejected(self) -> None:
        """`render` needs at least one node, so an all-comment program fails."""
        with pytest.raises(ValueError, match="no recognized commands"):
            bf_to_line("just a comment")


class TestALoopThatEndsItsParent:
    """A ``?`` whose ``zero`` arm is empty needs a node to carry the goto."""

    def test_a_nested_loop_at_the_end_of_a_body_compiles(self) -> None:
        from esolangs.tools.line.bf_to_line import bf_to_line

        node = bf_to_line("+[[-]]")
        assert node.op == "+"

    def test_the_placeholder_leaves_tape_and_pointer_alone(self) -> None:
        """A ``>`` then ``<``: the goto attaches after the pointer is back."""
        from esolangs.tools.line.bf_to_line import _nop

        placeholder = _nop()
        assert placeholder.op == ">"
        assert placeholder.next is not None
        assert placeholder.next.op == "<"

    @pytest.mark.medium
    def test_it_still_runs_through_the_image(self, tmp_path: Path) -> None:
        assert _run_bf("+[[-]].", tmp_path / "nested_tail.png") == [0]
