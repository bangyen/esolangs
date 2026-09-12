"""Tests for bf_to_line.py, driven through the *real* render pipeline.

Run via: uv run --with pytest pytest test_bf_to_line.py

This suite exists to close the coverage gap WIP.md flagged when the
nested-loop regression was found: `test_simulate.py` builds cyclic `Stroke`
trees directly from `lattice.py` primitives, so it exercises `simulate.py`'s
execution logic but never `render.py`'s actual loop-drawing geometry
(`_layout`/`_loop_return_legs`).  Every test here therefore goes the
whole way -- brainfuck source -> `bf_to_line` -> `render` -> `extract` ->
`simulate` -- since that full round trip is the only thing that can catch a
drawing whose *geometry* is wrong even though every individual module's own
logic is right.

The regression these were written against: a rendered loop-back reconnected
to its stem *perpendicularly*, which is pixel-for-pixel the same shape as the
wiki's T-branch, so `lattice._classify` read the merge as a real conditional
fork and `simulate` executed a jump as a branch.  Nested loops then silently
truncated -- `++[>++[>+<-]<-]>>.` computed the correct tape but halted before
its final `.` ever ran, printing nothing at all.  See
`render._DIAGONAL_APPROACH` (why a loop-back must land diagonally) and
`render._CLEARANCE` (why strokes must keep a mandated gap) for the two
distinct causes.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import render as render_module
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


def _max_between_stroke_adjacency(program: str) -> int:
    """Most cells of one stroke sitting flush against a *different* stroke.

    Captures the cursor's stroke list directly rather than measuring the
    rasterized image, so the count is in grid cells and names the two strokes
    involved unambiguously.  Strokes that genuinely share a cell (a fork's
    arms leaving its vertex, a detour's own merge point) are skipped: the
    failure mode being measured is two strokes running *parallel and
    adjacent* with no shared cell at all, which rasterizes into one
    contiguous 2px ribbon.

    Spies on `_Cursor.finish` rather than walking `render._layout`'s own
    structures: every stroke in the drawing -- op kinks, fork arms, and
    constructed loop-back returns, on the root cursor or a branch's --
    reaches the image by way of one `finish()` call, so recording there sees
    all of them without depending on where in the layout they were drawn.
    (This spy predates the constructed returns: when loop-backs were routed
    in a second phase after layout, `finish()` was the only chokepoint that
    saw both phases' strokes, and it remains the right one now that there is
    a single phase again.)
    """
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
    """Unrelated strokes must never be drawn flush against each other.

    `lattice._band_lit` deliberately probes the exact ray *plus one pixel to
    each side*, to absorb hand-drawn stroke slop -- so two strokes running
    parallel with no gap read as one another's lit direction, manufacturing
    a spurious junction the walker treats as a real fork.  Non-overlap alone
    is not enough; `render._CLEARANCE` is what enforces the gap.

    This pins `_CLEARANCE`, which was previously only reasoned about: it was
    kept at 1 on the strength of the band-probe argument, but no test
    asserted on stroke separation, so setting it to 0 left every test
    passing.  Measured directly, every program below develops between-stroke
    adjacency at `_CLEARANCE = 0` -- up to 76 consecutive abutting cells.
    """

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
        """No stroke touches a different stroke it does not share a cell with."""
        assert _max_between_stroke_adjacency(program) == 0


class TestNestingDepth:
    """Nesting depth is unbounded: loop-backs are constructed, not routed.

    This class used to be called `TestNestingDepthLimit` and pinned where
    the drawable depth stopped -- a boundary that moved from 3 to 4 to 5 to
    7 across successive routing fixes (measured corridors, a pixel-exact
    fallback, soft doorstep costs, ring fences -- see `WIP.md`'s depth-4 and
    depth-5 entries), each fix buying a level or two and exposing the next
    congestion.  The pattern itself was the finding: *search-based* routing
    competes for space globally, so every depth is a new fight.

    `render._loop_return_legs` ended the series by removing the search: a
    compiled brainfuck goto always ends its own fork's body chain, so its
    return path is constructed deterministically from measured geometry
    (wrap the body's bounding box, ride the reserved bay, land on the stem)
    -- and because `render._subtree_extent`'s dry runs draw the same
    construction, every ancestor's measured extent contains its children's
    return paths and reserves room for them recursively.  No routing, no
    congestion, no ceiling: depths 1-12 all round-trip (verified directly;
    depth 8 is pinned below as the deep representative, chosen for suite
    runtime -- rendering itself is ~10ms at any depth, the extract/simulate
    side is what grows).

    The invariant that survives from the original class is unchanged in
    substance: a drawing that cannot be completed fails loudly at render
    time rather than misdrawing.  A compiled program's loop-backs always
    construct, so :meth:`test_unconstructible_loop_back_raises` pins the
    invariant by forcing the construction to decline -- the shape a
    hand-built graph outside the compiled invariants would produce.
    """

    def test_three_levels_round_trip(self, tmp_path: Path) -> None:
        """Depth 3 renders, extracts and executes correctly.

        `+[>+[>+[>+<-]<-]<-]` moves a single 1 inward three times, so cell 3
        ends at 1; the trailing `>>>.` is what makes that observable as
        output rather than only as final tape state.  Asserting on printed
        output is deliberate -- the nested-loop regression this whole suite
        was written against computed the *correct tape* and still never
        reached its final `.`, so a tape-only assertion would have missed it.
        """
        assert _run_bf("+[>+[>+[>+<-]<-]<-]>>>.", tmp_path / "depth3.png") == [1]

    def test_heavy_three_levels_round_trip(self, tmp_path: Path) -> None:
        """A depth-3 body heavy enough to have exhausted the old router works.

        `++[>++[>++[>+<-]<-]<-]` is the same shape as the light case with
        doubled `+` runs, which stretch every arm; it computes 2*2*2 in cell
        3.  This is the program that pinned the *raise* under fork-count
        spacing -- it is here as a round-trip precisely because it is the case
        that used to fail, so a regression in extent-based spacing shows up as
        this test failing rather than as a silently larger drawing.
        """
        assert _run_bf("++[>++[>++[>+<-]<-]<-]>>>.", tmp_path / "d3heavy.png") == [8]

    def test_four_levels_round_trip(self, tmp_path: Path) -> None:
        """Depth 4 renders, extracts and executes correctly.

        The same inward-moving shape as the depth-3 case, one level deeper:
        cell 4 ends at 1 and `>>>>.` prints it.  This is the exact program
        whose failure `WIP.md`'s "Why depth 4 fails" entry instrumented cell
        by cell -- first pinned when three routing fixes made it drawable,
        and kept now that constructed loop-backs superseded them, exactly as
        the depth-3 programs were pinned when their boundary fell.
        """
        assert _run_bf("+[>+[>+[>+[>+<-]<-]<-]<-]>>>>.", tmp_path / "depth4.png") == [1]

    def test_five_levels_round_trip(self, tmp_path: Path) -> None:
        """Depth 5 renders, extracts and executes correctly.

        One level deeper again: cell 5 ends at 1 and `>>>>>.` prints it.
        This is the depth the free-form router could not reach at all (see
        `WIP.md`'s depth-5 entry) -- its depth-3 detour's shortest route
        sealed the depth-4 detour's region from 96% reachable to 5%.
        Pinned as a round-trip because it is the first depth only a
        construction-based loop-back can draw.
        """
        assert _run_bf(
            "+[>+[>+[>+[>+[>+<-]<-]<-]<-]<-]>>>>>.", tmp_path / "depth5.png"
        ) == [1]

    @pytest.mark.slow  # 5.2s: the deepest nesting the renderer draws
    def test_eight_levels_round_trip(self, tmp_path: Path) -> None:
        """Depth 8 renders, extracts and executes correctly.

        The deep representative for the constructed loop-back scheme --
        double the depth any routed version ever reached.  Depths up to 12
        were verified the same way when the construction landed; this one
        is pinned because extract/simulate time grows with drawing size and
        depth 8 keeps the suite fast (~1.6s) while still being unreachable
        by every search-based approach this file's history records.
        """
        assert _run_bf(
            "+[>+[>+[>+[>+[>+[>+[>+[>+<-]<-]<-]<-]<-]<-]<-]<-]>>>>>>>>.",
            tmp_path / "depth8.png",
        ) == [1]

    def test_unconstructible_loop_back_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A drawing that cannot complete fails loudly, never misdraws.

        This is the invariant the original `TestNestingDepthLimit` class was
        built around: an undrawable reconnection must be a loud render-time
        error, because the misdrawn alternative renders happily and then
        fails extraction thousands of unaccounted pixels later (or worse,
        executes wrongly).  A compiled program's loop-backs always
        construct, so the decline is forced here -- the shape a hand-built
        graph outside the compiled invariants (a goto whose target is not an
        ancestor fork whose body chain it ends, or a body end off its own
        box perimeter) would produce naturally.
        """
        monkeypatch.setattr(render_module, "_loop_return_legs", lambda *_a: None)
        with pytest.raises(ValueError, match="could not be constructed"):
            _run_bf("+++[-].", tmp_path / "unconstructible.png")


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
