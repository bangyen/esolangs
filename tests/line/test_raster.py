"""The public raster boundary exercised by Line."""

from pathlib import Path

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.line import run as run_line
from esolangs.raster import Raster
from esolangs.tools.line import line_boolean
from esolangs.tools.line.render import render


def test_png_round_trip_preserves_rgb() -> None:
    raster = Raster((((255, 0, 0), (0, 255, 0), (0, 0, 255)),))
    assert Raster.from_png(raster.to_png()) == raster


def test_raster_rejects_non_rectangular_rows() -> None:
    with pytest.raises(ValueError, match="equal-width"):
        Raster((((0, 0, 0),), ()))


def test_raster_rejects_an_invalid_channel() -> None:
    with pytest.raises(ValueError, match="8-bit RGB"):
        Raster((((0, 0, 256),),))


def test_raster_converts_to_greyscale() -> None:
    raster = Raster((((255, 0, 0), (0, 255, 0), (0, 0, 255)),))
    from esolangs.interpreters.tape_based.line import _grey_rows

    assert _grey_rows(raster.rows) == [bytearray([76, 150, 29])]


def test_greyscale_stays_correct_past_the_row_cache_limit() -> None:
    """Rows past the 1024-entry cache are converted uncached, not dropped."""
    from esolangs.interpreters.tape_based.line import _grey_rows

    rows = [((255, 0, 0), ((i + 3) % 256, 0, 0)) for i in range(1100)]
    grey = _grey_rows(rows)
    assert len(grey) == 1100
    assert all(
        row == bytearray([76, (((i + 3) % 256) * 19595 + 0x8000) >> 16])
        for i, row in enumerate(grey)
    )


@pytest.mark.medium
def test_line_consumes_the_public_raster() -> None:
    canvas = render(line_boolean("01"))
    raster = Raster(
        tuple(tuple((level, level, level) for level in row) for row in canvas.pixels)
    )
    io = ScriptedIO("1\n")
    run_line(raster, io)
    assert io.getvalue() == "1"


def test_line_is_a_public_raster_language() -> None:
    program = esolangs.generate("Line", "01")
    assert isinstance(program, Raster)
    assert esolangs.describe("Line")["source_kind"] == "raster"
    assert esolangs.run("Line", program, "1\n") == "1"


@pytest.mark.slow
def test_public_run_loads_line_png(tmp_path: Path) -> None:
    program = esolangs.generate("Line", "01")
    assert isinstance(program, Raster)
    path = tmp_path / "line.png"
    path.write_bytes(program.to_png())
    assert esolangs.run("Line", path, "0\n") == "0"


def test_a_corrupt_png_is_a_value_error(tmp_path: Path) -> None:
    """The decoder's raw zlib/struct errors used to escape ``load_binary``."""
    from esolangs.interpreters.tape_based.line import extract

    path = tmp_path / "corrupt.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
    with pytest.raises(ValueError, match="cannot read"):
        extract.load_binary(str(path))


def test_verify_finds_its_fixtures() -> None:
    """The old path did not exist, so the script verified nothing and passed."""
    from scripts import verify_line_fixtures as verify

    assert verify.FIXTURES.is_dir()
    assert list(verify.FIXTURES.glob("*.png"))


def test_verify_fails_when_there_is_nothing_to_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty sweep is not a pass."""
    from scripts import verify_line_fixtures as verify

    assert verify.main(tmp_path) == 1
    assert "no fixtures" in capsys.readouterr().err


def test_verify_reports_a_fixture_that_does_not_extract(tmp_path: Path) -> None:
    """The pass/fail loop itself, on an image that is not a Line program."""
    from scripts import verify_line_fixtures as verify

    (tmp_path / "blank.png").write_bytes(Raster((((0, 0, 0),),)).to_png())
    assert verify.main(tmp_path) == 1


def test_verify_passes_on_the_committed_fixtures(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The green path of the fixture sweep, which only its failures had."""
    from scripts import verify_line_fixtures as verify

    assert verify.main() == 0
    out = capsys.readouterr().out
    assert out
    assert all(line.endswith(": ok") for line in out.splitlines())


def test_a_generated_raster_runs_from_its_retained_graph() -> None:
    """``run`` short-circuits to the graph when the raster carries one."""
    from esolangs.tools.line import line as generate

    program = generate("0110")
    assert program._payload is not None  # noqa: SLF001
    io = ScriptedIO("1\n0\n")
    run_line(program, io)
    assert io.getvalue() == "1"


@pytest.mark.medium  # 0.97s alone: renders and walks the pixels
def test_the_graph_walker_matches_the_pixels() -> None:
    """Both routes answer the same, which is what makes the shortcut safe."""
    from esolangs.tools.line import line as generate

    program = generate("0110")
    through_graph = ScriptedIO("1\n1\n")
    run_line(program, through_graph)

    through_pixels = ScriptedIO("1\n1\n")
    run_line(Raster(program.rows), through_pixels)

    assert through_graph.getvalue() == through_pixels.getvalue() == "0"


def test_the_graph_walker_decrements() -> None:
    """``-`` is the one opcode no generated Line program emits."""
    from esolangs.interpreters.tape_based.line import _Machine
    from esolangs.tools.line.render import Node

    minus = Node("-")
    minus.next = Node("o")
    start = Node("+")
    start.next = minus

    io = ScriptedIO()
    _Machine.run_node(start, io)
    assert io.getvalue() == "0"


def test_the_graph_walker_steps_over_an_opcode_it_does_not_know() -> None:
    """Characterizing the fall-through: an unknown op advances, silently."""
    from esolangs.interpreters.tape_based.line import _Machine
    from esolangs.tools.line.render import Node

    start = Node("!")
    start.next = Node("o")

    io = ScriptedIO()
    _Machine.run_node(start, io)
    assert io.getvalue() == "0"


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [("addition.png", [5, 4, 5]), ("multiplication.png", [6, 0, 6])],
)
def test_public_and_bounded_runs_reuse_pixels_with_fresh_state(
    fixture: str, expected: list[int], monkeypatch: pytest.MonkeyPatch
) -> None:
    import esolangs.interpreters.tape_based.line as line

    source = Raster.from_png(
        (Path(__file__).parents[1] / "fixtures" / "line" / fixture).read_bytes()
    )
    line._compiled.cache_clear()  # noqa: SLF001
    original = line.extract_mask
    parses = 0

    def extract_once(*args, **kwargs):
        nonlocal parses
        parses += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(line, "extract_mask", extract_once)
    for (a, b), answer in zip([(3, 2), (0, 4), (2, 3)], expected, strict=True):
        stdin = f"{a}\n{b}\n"
        assert esolangs.run("Line", source, stdin) == str(answer)
        assert esolangs.run("Line", source, stdin, max_steps=1000) == str(answer)
    assert parses == 1
    line._compiled.cache_clear()  # noqa: SLF001


def test_line_infers_the_entry_heading_from_the_arrow() -> None:
    """Pins heading inference: rotated a quarter turn clockwise, the
    ``01`` program still enters along its path (east), not forced north."""
    pixels = render(line_boolean("01")).pixels
    turned = [list(row) for row in zip(*pixels[::-1], strict=True)]
    raster = Raster(tuple(tuple((v, v, v) for v in row) for row in turned))
    for bit in "01":
        io = ScriptedIO(f"{bit}\n")
        run_line(raster, io)
        assert io.getvalue() == bit
