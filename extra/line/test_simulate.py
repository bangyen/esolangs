"""Tests for simulate.py.

Run via: uv run --with pytest pytest test_simulate.py

Captures the checks this module's own development relied on ad hoc (see
WIP.md's "Runtime simulation" entry for the full history): opcode basics
through a real render->extract round-trip, the zero/nonzero swap between
lattice.py's field names and the wiki's actual "turn right if 0" rule,
both wiki fixtures computing correct results across several real inputs
(the thing an earlier, wrong version of this module's loop detection got
silently wrong), the synthetic loop-back mechanism itself (neither
render.py nor either wiki fixture alone proves it in isolation from real
geometry), and non-termination actually hanging rather than raising or
returning a wrong answer.
"""

from __future__ import annotations

import signal
from collections.abc import Iterator
from pathlib import Path

import pytest
from extract import crop_to_content, detect_scale, extract, load_binary
from lattice import _DIRS, Stroke, Vertex
from render import Node, chain, render
from simulate import IO, run

# Anchored to this file rather than the working directory, so the wiki
# fixtures resolve no matter where pytest is invoked from.
FIXTURES = str(Path(__file__).parent / "fixtures")


def _io(inputs: list[int]) -> tuple[IO, list[int]]:
    outputs: list[int] = []
    values: Iterator[int] = iter(inputs)
    return IO(read=values.__next__, write=outputs.append), outputs


class TestBasicOps:
    """Opcode basics through a real render -> extract -> simulate round-trip."""

    def test_plus_repeats_merge_into_one_count(self, tmp_path: Path) -> None:
        """Three consecutive `+` render as one merged kink, still count=3."""
        path = str(tmp_path / "plusplusplus.png")
        render(chain("+", "+", "+")).save(path)
        tape = run(extract(path))
        assert tape.get(0, 0) == 3

    def test_pointer_movement_and_increment_across_cells(self, tmp_path: Path) -> None:
        """`>` moves the pointer; `+` increments whichever cell it lands on."""
        path = str(tmp_path / "move.png")
        render(chain(">", "+", "+", "<", "+")).save(path)
        tape = run(extract(path))
        assert tape.get(0, 0) == 1
        assert tape.get(1, 0) == 2


class TestRenderScale:
    """`render(scale=k)` thickens strokes without changing the program.

    The point of the parameter is surviving lossy storage (see render()'s
    docstring for the measured JPEG quality cliffs), which these cannot test
    without an image library -- so what is guarded here is the invariant that
    makes it safe to use at all: a scaled drawing must extract to exactly the
    program the 1x drawing does.
    """

    @pytest.mark.parametrize("scale", [1, 2, 3, 4])
    def test_scaled_render_extracts_the_same_program(
        self, scale: int, tmp_path: Path
    ) -> None:
        """Every scale round-trips to the same tape as 1x."""
        path = str(tmp_path / f"scaled{scale}.png")
        render(chain(">", "+", "+", "<", "+"), scale=scale).save(path)
        tape = run(extract(path))
        assert tape.get(0, 0) == 1
        assert tape.get(1, 0) == 2

    @pytest.mark.parametrize("scale", [2, 3])
    def test_scale_multiplies_the_canvas_exactly(self, scale: int) -> None:
        """Pixel replication, so dimensions are an exact integer multiple."""
        base = render(chain("+", "+", "+"))
        scaled = render(chain("+", "+", "+"), scale=scale)
        assert (scaled.width, scaled.height) == (
            base.width * scale,
            base.height * scale,
        )

    def test_scale_is_recoverable_by_the_extractor(self, tmp_path: Path) -> None:
        """detect_scale reads back the exact factor rendered at.

        This is the property the whole parameter rests on: normalize_scale
        divides out what detect_scale finds, so an off-by-one here would feed
        the walker a drawing at the wrong resolution.
        """
        path = str(tmp_path / "three_x.png")
        render(chain("+", "+", "+"), scale=3).save(path)
        assert detect_scale(crop_to_content(load_binary(path))) == 3

    @pytest.mark.parametrize("bad", [0, -1])
    def test_a_nonsense_scale_is_refused(self, bad: int) -> None:
        """Zero or negative would silently produce an empty or absurd canvas."""
        with pytest.raises(ValueError, match="at least 1"):
            render(chain("+"), scale=bad)


class TestConditionalBranch:
    """Confirms the zero/nonzero swap documented in run()'s docstring.

    lattice.py's Stroke.zero/Stroke.nonzero field names are rotated 180
    degrees from the wiki's "turn right if 0" rule, so a render.py-drawn
    `zero` arm (which render.py draws turning right, matching the wiki)
    round-trips into the walked tree's `nonzero` field.  These exercise
    both directions of that swap through a real round-trip, not just by
    reading the code.
    """

    @pytest.fixture
    def tree(self, tmp_path: Path) -> Stroke:
        """Render a `?` with distinct, easily-told-apart zero/nonzero arms."""
        path = str(tmp_path / "branch.png")
        node = Node("?", zero=chain("+", "+"), nonzero=chain("-", ">"))
        render(Node("i", next=node)).save(path)
        return extract(path)

    def test_zero_cell_takes_the_plus_plus_arm(self, tree: Stroke) -> None:
        """A zero input cell runs the `++` arm, not the `-` `>` one."""
        io, _ = _io([0])
        tape = run(tree, io=io)
        assert tape.get(0, 0) == 2

    def test_nonzero_cell_takes_the_minus_greater_arm(self, tree: Stroke) -> None:
        """A nonzero input cell runs the `-` `>` arm, not the `++` one."""
        io, _ = _io([5])
        tape = run(tree, io=io)
        assert tape.get(0, 0) == 4
        assert tape.get(1, 0) == 0


class TestWikiFixtures:
    """Both wiki fixtures compute correct results across several real inputs.

    An earlier version of this module's merge detection only matched an
    exact vertex coordinate, missed addition.png's loop-body arm (which
    merges back into the *middle* of the incoming stem's own path, not
    onto any recorded vertex), and silently reported both fixtures as
    single-pass/loop-free -- confirmed wrong only by actually running them
    with real inputs and checking the arithmetic, which is exactly what
    these tests do.
    """

    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [(3, 2, 5), (0, 0, 0), (7, 3, 10), (10, 10, 20), (0, 1, 1)],
    )
    def test_addition(self, a: int, b: int, expected: int) -> None:
        """addition.png computes a + b for several input pairs, including 0."""
        io, outputs = _io([a, b])
        run(extract(f"{FIXTURES}/addition.png"), io=io)
        assert outputs == [expected]

    @pytest.mark.parametrize(
        ("a", "b", "expected"),
        [(3, 2, 6), (4, 4, 16), (0, 5, 0)],
    )
    def test_multiplication(self, a: int, b: int, expected: int) -> None:
        """multiplication.png computes a * b for several input pairs."""
        io, outputs = _io([a, b])
        run(extract(f"{FIXTURES}/multiplication.png"), io=io)
        assert outputs == [expected]


def _build_decrement_loop() -> Stroke:
    """Build a synthetic ``+++`` seed forking into a decrementing loop or a halt.

    Built directly from lattice.py primitives (bypassing render.py, which
    cannot produce a real cyclic Node graph -- see WIP.md) so the loop-back
    mechanism itself is testable independent of any real fixture's
    geometry.  The loop arm's own final vertex is placed exactly on the
    fork's own final vertex -- the "landing exactly on another stroke's
    final vertex" case, which addition.png's own merge does *not* exercise
    (that one lands strictly inside a segment instead) -- so together the
    two give both of find_merge's match branches their own coverage.
    """
    unit = 20
    heading = 0
    turn_minus = (heading - 1) % 8
    dy, dx = _DIRS[turn_minus]
    turn_plus = (heading + 1) % 8
    pdy, pdx = _DIRS[turn_plus]

    root_v0 = Vertex(0, 0, heading)
    root_v1 = Vertex(-unit, 0, turn_plus)
    fork_y = -unit + pdy * 3 * unit
    fork_x = pdx * 3 * unit
    root_v2 = Vertex(fork_y, fork_x, heading)
    root_v3 = Vertex(fork_y - unit, fork_x, None)
    fy, fx = root_v3.y, root_v3.x

    v0 = Vertex(fy, fx, heading)
    v1 = Vertex(fy - unit, fx, turn_minus)
    v2 = Vertex(fy - unit + dy * unit, fx + dx * unit, heading)
    v3 = Vertex(fy, fx, None)
    loop_arm = Stroke(vertices=[v0, v1, v2, v3])
    halt_arm = Stroke(
        vertices=[Vertex(fy, fx, turn_plus), Vertex(fy + 5, fx + 5, None)]
    )

    root = Stroke(vertices=[root_v0, root_v1, root_v2, root_v3])
    # The loop body is the *nonzero* arm: a loop repeats while the cell is
    # nonzero and falls through to the halt arm once it reads zero.  (These
    # two were reversed while `lattice._classify` named its fork arms off
    # `back` rather than the heading, which inverted every label and made
    # `simulate.run` swap the children to compensate.)
    root.nonzero = loop_arm
    root.zero = halt_arm
    return root


def _build_growing_loop() -> Stroke:
    """Like _build_decrement_loop, but the loop arm increments -- never halts."""
    unit = 20
    heading = 0
    turn_plus = (heading + 1) % 8
    dy, dx = _DIRS[turn_plus]

    fork_y, fork_x = -2 * unit, 0
    v0 = Vertex(fork_y, fork_x, heading)
    v1 = Vertex(fork_y - unit, fork_x, turn_plus)
    v2 = Vertex(fork_y - unit + dy * unit, fork_x + dx * unit, heading)
    v3 = Vertex(fork_y, fork_x, None)
    loop_arm = Stroke(vertices=[v0, v1, v2, v3])
    turn_minus = (heading - 1) % 8
    halt_arm = Stroke(
        vertices=[
            Vertex(fork_y, fork_x, turn_minus),
            Vertex(fork_y + 5, fork_x - 5, None),
        ]
    )

    s0 = Vertex(0, 0, heading)
    s1 = Vertex(-unit, 0, turn_plus)
    s2 = Vertex(-unit + dy * unit, dx * unit, heading)
    s3 = Vertex(fork_y, fork_x, None)
    root = Stroke(vertices=[s0, s1, s2, s3])
    # The loop body is the *nonzero* arm: a loop repeats while the cell is
    # nonzero and falls through to the halt arm once it reads zero.  (These
    # two were reversed while `lattice._classify` named its fork arms off
    # `back` rather than the heading, which inverted every label and made
    # `simulate.run` swap the children to compensate.)
    root.nonzero = loop_arm
    root.zero = halt_arm
    return root


class TestSyntheticLoopMechanism:
    """The loop-back mechanism itself, independent of any real fixture's geometry."""

    def test_decrementing_loop_terminates_at_zero(self) -> None:
        """A synthetic loop decrementing its seed cell halts exactly at 0."""
        io, _ = _io([])
        tape = run(_build_decrement_loop(), io=io)
        assert tape.get(0, 0) == 0

    def test_non_halting_loop_hangs_rather_than_returning(self) -> None:
        """A loop with no reachable dead end hangs, per run()'s own docstring."""

        def _timeout_handler(_signum: int, _frame: object) -> None:
            raise TimeoutError

        old = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.setitimer(signal.ITIMER_REAL, 1.0)
        try:
            with pytest.raises(TimeoutError):
                run(
                    _build_growing_loop(),
                    io=IO(read=lambda: 0, write=lambda _v: None),
                )
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, old)

    def test_loop_back_does_not_match_an_unrelated_sibling_branch(self) -> None:
        """Regression: a bare vertex match once matched an untaken sibling.

        `halt_arm` starts at the same fork coordinate as the real ancestor
        fork, since every fork's children start exactly where the fork
        itself ends.  Already covered by
        ``test_decrementing_loop_terminates_at_zero`` above (it would
        infinite-loop or return a wrong tape if this regressed); named
        separately so a future regression here has an obviously-relevant
        failing test.
        """
        io, _ = _io([])
        tape = run(_build_decrement_loop(), io=io)
        assert tape == {0: 0}
