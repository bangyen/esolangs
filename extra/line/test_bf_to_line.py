"""Tests for bf_to_line.py, driven through the *real* render pipeline.

Run via: uv run --with pillow --with numpy --with scipy --with scikit-image
--with pytest pytest test_bf_to_line.py

This suite exists to close the coverage gap WIP.md flagged when the
nested-loop regression was found: `test_simulate.py` builds cyclic `Stroke`
trees directly from `lattice.py` primitives, so it exercises `simulate.py`'s
execution logic but never `render.py`'s actual loop-drawing geometry
(`_layout`/`_close_loop`/`_route_legs`).  Every test here therefore goes the
whole way -- brainfuck source -> `bf_to_line` -> `render` -> `extract` ->
`simulate` -- since that full round trip is the only thing that can catch a
drawing whose *geometry* is wrong even though every individual module's own
logic is right.

The regression these were written against: a rendered loop-back reconnected
to its stem *perpendicularly*, which is pixel-for-pixel the same shape as the
wiki's T-branch, so `lattice._classify` read the merge as a real conditional
fork and `simulate` executed a jump as a branch.  Nested loops then silently
truncated -- `++[>++[>+<-]<-]>>.` computed the correct tape but halted before
its final `.` ever ran, printing nothing at all.  See `render._approach_points`
and `render._CLEARANCE`/`_self_approaches` for the two distinct causes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bf_to_line import bf_to_line
from extract import extract
from render import render
from simulate import IO, run


def _run_bf(program: str, path: Path, inputs: list[int] | None = None) -> list[int]:
    """Compile, draw, re-extract and execute ``program``, returning its output.

    Deliberately routes through the real image: rendering to a PNG and
    reading it back with :func:`extract.extract` is what makes these tests
    cover drawing geometry rather than just the in-memory ``Node`` graph.
    """
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
    """One level of `[...]`, drawn as a real reconnecting stroke.

    These passed before the nested-loop fix, but only by accident: their
    merge point classified as a spurious `"fork"` exactly like the nested
    case, and survived only because both bogus arms happened to land on
    already-visited vertices, degrading the stroke back to a leaf.  They are
    kept as regression cover for that accident becoming real behavior.
    """

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
    """Two levels of real `[...]` -- the case WIP.md recorded as broken.

    `++[>++[>+<-]<-]>>.` computes 2*2 into cell 2.  Before the fix it built
    the correct tape but never reached its own final `.`, so it printed
    nothing; asserting on the *output* (not just the tape) is what makes
    this test actually cover the regression.
    """

    def test_nested_multiply_prints_result(self, tmp_path: Path) -> None:
        """The exact program WIP.md recorded as silently truncating."""
        assert _run_bf("++[>++[>+<-]<-]>>.", tmp_path / "nested.png") == [4]

    def test_nested_loop_reaches_code_after_outer_loop(self, tmp_path: Path) -> None:
        """The op *after* a nested loop still runs -- the exact truncation seen."""
        assert _run_bf("++[>++[>+<-]<-]>>+++.", tmp_path / "nested_tail.png") == [7]


class TestCompileErrors:
    """`bf_to_line`'s own documented rejections, no rendering involved."""

    @pytest.mark.parametrize("program", ["[", "+[+", "]", "+]"])
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
