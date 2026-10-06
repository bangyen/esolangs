"""Tests for simulate.py."""

from __future__ import annotations

import signal
from collections.abc import Iterator
from inspect import signature
from pathlib import Path

import pytest

from esolangs.interpreters.tape_based.line import lattice
from esolangs.interpreters.tape_based.line.extract import (
    crop_to_content,
    detect_scale,
    extract,
    find_cursor,
    load_binary,
)
from esolangs.interpreters.tape_based.line.lattice import _DIRS, Stroke, Vertex
from esolangs.interpreters.tape_based.line.mask import Mask, from_grey
from esolangs.interpreters.tape_based.line.simulate import IO, run
from esolangs.raster.png import read_grey
from esolangs.tools.line.render import Node, chain, render


def test_transition_preserves_prior_states_and_requests_output() -> None:
    from esolangs.interpreters.tape_based.line.simulate import _advance, _Frame

    program = (_Frame((("i", 1), ("+", 2), ("o", 1)), (), (0, 0), None, None, None),)
    initial = (0, 0, 0, ())
    entered, output = _advance(initial, program, 3)
    assert output is None
    assert _advance(initial, program, 3) == (entered, None)
    changed, _ = _advance(entered, program)
    emitted, output = _advance(changed, program)
    assert output == 5
    assert initial == (0, 0, 0, ())
    assert entered == (0, 1, 0, ((0, 3),))
    assert changed == (0, 2, 0, ((0, 5),))
    halted, _ = _advance(emitted, program)
    assert _advance(halted, program) == (halted, None)
    with pytest.raises(ValueError, match="requires a value"):
        _advance(initial, program)


# Anchored to this file rather than the working directory, so the wiki
# fixtures resolve no matter where pytest is invoked from.
FIXTURES = str(Path(__file__).parents[1] / "fixtures" / "line")
INVALID_FIXTURES = Path(__file__).parents[1] / "fixtures" / "line_invalid"


def test_lattice_probe_length_is_derived_from_unit() -> None:
    """The star probe keeps its quarter-unit clearance at smaller units."""
    default = signature(lattice.star).parameters["length"].default
    assert default == max(1, lattice.UNIT * 3 // 4)


def test_a_straight_run_is_walked_to_its_end_however_long() -> None:
    """`_walk_segment` has no fixed ceiling: stopping short invents a vertex."""
    height, width = 640, 3
    column = Mask(height, width, [0b010 if 10 <= y < 610 else 0 for y in range(height)])
    assert lattice._walk_segment(column, 10, 1, 4) == (609, 1)  # noqa: SLF001 - unit under test


def _io(inputs: list[int]) -> tuple[IO, list[int]]:
    outputs: list[int] = []
    values: Iterator[int] = iter(inputs)
    return IO(read=values.__next__, write=outputs.append), outputs


class TestCursorSelection:
    """Cursor detection refuses images whose start cannot be determined."""

    def test_two_arrowheads_are_ambiguous(self) -> None:
        """Two complete drawings supply two equally plausible cursors."""
        drawing = from_grey(render(chain("+")).pixels)
        offset = drawing.width + 10
        mask = Mask(
            drawing.height,
            drawing.width * 2 + 10,
            [row | (row << offset) for row in drawing.rows],
        )
        with pytest.raises(ValueError, match="ambiguous cursor: found 2"):
            find_cursor(mask)

    def test_larger_non_arrow_blob_does_not_hide_cursor(self) -> None:
        """Shape, not component size alone, selects the sole arrowhead."""
        drawing = from_grey(render(chain("+")).pixels)
        rows = list(drawing.rows)
        square = ((1 << 12) - 1) << (drawing.width + 4)
        for y in range(2, 14):
            rows[y] |= square
        mask = Mask(drawing.height, drawing.width + 16, rows)
        assert find_cursor(mask).x < drawing.width


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
    """`render(scale=k)` thickens strokes without changing the program."""

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

    def test_scale_is_recoverable_by_the_extractor(self, tmp_path: Path) -> None:
        """detect_scale reads back the exact factor rendered at."""
        path = str(tmp_path / "three_x.png")
        render(chain("+", "+", "+"), scale=3).save(path)
        assert detect_scale(crop_to_content(load_binary(path))) == 3


class TestConditionalBranch:
    """Confirms the zero/nonzero swap documented in run()'s docstring."""

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
    """Both wiki fixtures compute correct results across several real inputs."""

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

    def test_antialiased_scan(self) -> None:
        """Softened 3px strokes retain their program and arithmetic."""
        path = Path(FIXTURES) / "addition_antialiased_3x.png"
        levels = {level for row in read_grey(path.read_bytes()) for level in row}
        assert len(levels) == 12
        stroke = extract(str(path))
        for a, b in ((3, 2), (0, 5), (7, 3)):
            io, outputs = _io([a, b])
            run(stroke, io=io)
            assert outputs == [a + b]


def test_antialiased_resample_is_rejected() -> None:
    """A resample that erases the stroke core fails instead of changing it."""
    path = INVALID_FIXTURES / "addition_antialiased.png"
    levels = {level for row in read_grey(path.read_bytes()) for level in row}
    assert len(levels) == 194
    with pytest.raises(ValueError, match="left 921 source pixels unaccounted"):
        extract(str(path))


def _build_decrement_loop() -> Stroke:
    """Build a synthetic ``+++`` seed forking into a decrementing loop or a halt."""
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

    @pytest.mark.slow  # 1.0s: it runs the interpreter into its step ceiling
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
        """Regression: a bare vertex match once matched an untaken sibling."""
        io, _ = _io([])
        tape = run(_build_decrement_loop(), io=io)
        assert tape == {0: 0}


@pytest.mark.parametrize("fixture", ["addition.png", "multiplication.png"])
def test_pixel_vm_matches_the_native_arithmetic_fixture(fixture: str) -> None:
    from esolangs import run as public_run
    from esolangs.raster import Raster
    from esolangs.vm import make_vm, run_until_halt

    source = Raster.from_png((Path(FIXTURES) / fixture).read_bytes())
    stdin = "3\n2\n"
    vm = make_vm("Line", source, stdin)
    assert run_until_halt(vm, 1000)
    assert vm.output == public_run("Line", source, stdin)
    assert vm.output == ("5" if fixture == "addition.png" else "6")


def test_compiled_missing_fork_arm_halts() -> None:
    from esolangs.interpreters.tape_based.line.simulate import (
        compile_program,
        run_compiled,
    )

    root = Stroke(vertices=[Vertex(0, 0, 0), Vertex(-20, 0, None)])
    root.nonzero = Stroke(vertices=[Vertex(-20, 0, 0), Vertex(-40, 0, None)])
    io, outputs = _io([])
    assert run_compiled(compile_program(root), io=io) == {0: 0}
    assert outputs == []


def test_two_merges_into_one_leg_share_the_resume_position() -> None:
    from esolangs.interpreters.tape_based.line.simulate import compile_program

    root = _build_decrement_loop()
    start, end = root.vertices[1:3]
    fork = root.vertices[-1]
    arms = []
    for fraction in (1, 2):
        point = Vertex(
            start.y + (end.y - start.y) * fraction // 3,
            start.x + (end.x - start.x) * fraction // 3,
            None,
        )
        arms.append(Stroke(vertices=[Vertex(fork.y, fork.x, 0), point]))
    root.zero, root.nonzero = arms
    compiled = compile_program(root)
    assert compiled.zero is not None
    assert compiled.nonzero is not None
    assert compiled.zero.goto is not None
    assert compiled.zero.goto is compiled.nonzero.goto
    assert compiled.zero.goto.positions == ()


@pytest.mark.parametrize(
    ("y", "x", "direction", "expected"),
    [
        (1, 0, 0, True),
        (1, 1, 0, True),
        (1, 2, 0, True),
        (0, 0, 1, True),
        (0, 0, 0, False),
        (-2, 0, 0, False),
        (3, 1, 0, False),
        (1, -2, 0, False),
        (1, 4, 0, False),
    ],
)
def test_band_probe_preserves_edges_and_all_three_rays(y, x, direction, expected):
    mask = Mask(3, 3, [0, 2, 0])
    assert lattice._band_lit(mask, y, x, direction) is expected  # noqa: SLF001


def test_lattice_preserves_an_unsnappable_start_and_stops_a_zero_length_stroke() -> (
    None
):
    mask = Mask(3, 3)
    assert lattice._snap(mask, 1, 1, 0) == (1, 1)  # noqa: SLF001
    stroke = lattice.walk_tree(mask, (1, 1), 0)
    assert stroke.end == (1, 1)
    assert len(stroke.vertices) == 2


def test_lattice_crossing_keeps_the_arrival_heading() -> None:
    assert lattice._classify({0, 2, 4, 6}, 4) == ("crossing", [0])  # noqa: SLF001


@pytest.mark.parametrize("visited", [set(), {(20, 0)}, {(20, 40)}, {(20, 0), (20, 40)}])
def test_lattice_fork_does_not_rewalk_visited_arm_endpoints(visited) -> None:
    mask = Mask(41, 41)
    for y in range(20, 41):
        mask[y, 20] = True
    for x in range(41):
        mask[20, x] = True
    seen = set(visited)
    stroke = lattice.walk_tree(mask, (40, 20), 0, seen)
    assert stroke.end == (20, 20)
    assert (stroke.zero is None) == ((20, 40) in visited)
    assert (stroke.nonzero is None) == ((20, 0) in visited)
