"""Line through the shared API, CLI and machinery."""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs import Raster, run
from esolangs.cli import main
from esolangs.languages.line.interpreter.extract import detect_scale, normalize_scale
from esolangs.languages.line.interpreter.mask import Mask
from tests.support.cli_support import call_main
from tests.support.evaluation import _evaluate
from tests.support.input_convention import assert_reads_tokens_on_one_line
from tests.support.reference import REFERENCE


@pytest.mark.medium
@pytest.mark.parametrize("scale", [1, 2])
def test_cli_scaled_raster(capsysbinary, scale) -> None:
    argv = ["esolangs", "generate", "--scale", str(scale), "Line", "0110"]
    with patch.object(sys, "argv", argv):
        main()
    image = Raster.from_png(capsysbinary.readouterr().out)
    assert _evaluate("Line", image, inputs=2) == "0110"


@pytest.mark.medium
@pytest.mark.parametrize("scale", [1, 2])
def test_raw_png_round_trip_executes(scale, tmp_path) -> None:
    settings = esolangs.Language("Line").settings()
    source = esolangs.generate("Line", "01", scale=scale, settings=settings)
    path = tmp_path / "program.png"
    esolangs.to_file("Line", source, path)
    raw = esolangs.Language("Line").from_file(path)
    assert raw.settings == settings
    assert raw.scale == scale
    assert Raster.from_png(path.read_bytes()).rows == raw.source.rows
    assert not hasattr(raw.source, "settings")
    restored = esolangs.load_program(
        "Line", esolangs.dump_program("Line", raw, settings=settings)
    )
    assert isinstance(restored, esolangs.ProgramArtifact)
    assert restored.source.rows == source.source.rows
    assert _evaluate("Line", restored, inputs=1) == "01"


@pytest.mark.parametrize("value", ["!", "abcd", "é"])
def test_invalid_png(value) -> None:
    document = json.loads(
        esolangs.dump_program("Line", esolangs.generate("Line", "01"))
    )
    document["source"] = value
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Line", json.dumps(document))


class TestTheSmallInconsistencies:
    """Each one was a place this CLI did not do what it does everywhere else."""

    def test_a_repeated_isolated_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Every value-taking option refused a repeat; this flag did not."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate(REFERENCE, "0110").source)
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--isolated", "--isolated", REFERENCE, str(path)],
                capsys,
                stdin="0\n1\n",
            )
        assert exc.value.code == 2
        assert "--isolated given more than once" in capsys.readouterr().err

    @pytest.mark.medium
    def test_a_no_op_width_says_so(
        self, capsysbinary: pytest.CaptureFixture[bytes]
    ) -> None:
        with (
            patch.object(
                sys, "argv", ["esolangs", "generate", "--width", "10", "Line", "0100"]
            ),
            patch.object(sys, "stdin", StringIO("")),
        ):
            main()
        captured = capsysbinary.readouterr()
        assert b"no effect on Line" in captured.err
        image = esolangs.Raster.from_png(captured.out)
        assert run("Line", image, stdin="0\n0\n").output == "0"


def test_source_kind_cannot_change_language_contract() -> None:
    document = json.loads(
        esolangs.dump_program("Line", esolangs.generate("Line", "01"))
    )
    document["language"] = REFERENCE
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Brainfuck", json.dumps(document))


@pytest.mark.medium
def test_raster_interpreter_retains_geometry_hint() -> None:
    image = Raster((((255, 255, 255),),))
    with pytest.raises(esolangs.ProgramError, match=r".+") as caught:
        run(
            "Line",
            image,
            scale=None,
            limits=esolangs.ExecutionLimits(execution_timeout=1),
        )
    assert "dark connected paths" in caught.value.__notes__[0]


def test_line_detection_has_no_sixteen_fold_ceiling() -> None:
    # A small stroke with uneven outer margins retains its ink-anchored grid.
    mask = Mask(
        40,
        45,
        [0] * 3 + [((1 << 34) - 1) << 5] * 17 + [((1 << 17) - 1) << 5] * 17 + [0] * 3,
    )
    assert detect_scale(mask) == 17


def test_a_one_pixel_path_below_a_stair_stepped_arrowhead_keeps_scale_one() -> None:
    # Only the last row is one pixel thick, so only it shows the scale is 1.
    art = [
        "....##........",
        "....##........",
        "..######......",
        "..######......",
        "##########....",
        "##############",
    ]
    ink, blank = (0, 0, 0), (255, 255, 255)
    image = Raster(tuple(tuple(ink if c == "#" else blank for c in r) for r in art))
    assert run("Line", image).output == ""


def test_a_two_pixel_speck_nearer_than_the_path_is_not_the_path() -> None:
    # Extraction tolerates two stray pixels; they must not be read as the path.
    rows = [list(row) for row in esolangs.generate("Line", "01").source.rows]
    for y in (1, 2):
        rows[y][51] = (0, 0, 0)
    image = Raster(tuple(map(tuple, rows)))
    assert run("Line", image, stdin="0\n").output == "0"
    assert run("Line", image, stdin="1\n").output == "1"


def test_explicit_line_scale_checks_ink_blocks() -> None:
    with pytest.raises(ValueError, match="uniform"):
        normalize_scale(Mask(3, 2, [3, 3, 3]), 2)
    blank = Mask(3, 3)
    assert normalize_scale(blank, 2) is blank
    # A partly blank group is still uniform.
    assert normalize_scale(Mask(3, 2, [3, 3, 0]), 2).rows == [1, 0]


@pytest.mark.medium
def test_explicit_scale_validates_lazy_line_pixels() -> None:
    image = esolangs.generate("Line", "00", scale=2)
    assert run("Line", image, stdin="1\n", scale=2).output == "0"
    assert (
        run("Line", Raster.from_png(image.source.to_png()), stdin="1\n").output == "0"
    )
    with pytest.raises(esolangs.ProgramError, match="uniform"):
        run("Line", image, stdin="1\n", scale=3)


def test_it_reads_numeric_tokens_on_the_same_line() -> None:
    assert_reads_tokens_on_one_line("Line")
