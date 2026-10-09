"""Line through the shared API, CLI and machinery."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs import DialectSettings, Raster
from esolangs._evaluate import _evaluate
from esolangs.cli import main
from esolangs.interpreters.tape_based.line.extract import detect_scale, normalize_scale
from esolangs.interpreters.tape_based.line.mask import Mask
from esolangs.tui import History, render
from tests.cli.test_cli import _FakeStdin, call_main
from tests.cli.test_cli_portable import save_generated
from tests.cli_support import call_both
from tests.interpreters.test_input_convention import assert_reads_tokens_on_one_line
from tests.test_tui import _highlighted


@pytest.mark.medium
@pytest.mark.parametrize("scale", [1, 2])
def test_cli_scaled_raster(tmp_path, capsys, scale):
    settings = DialectSettings()
    path = save_generated(tmp_path, capsys, "Line", settings, "--scale", str(scale))
    restored = esolangs.load_program("Line", path.read_text(encoding="utf-8"))
    assert _evaluate("Line", restored, inputs=2) == "0110"


@pytest.mark.medium
@pytest.mark.parametrize("scale", [1, 2])
def test_raw_png_round_trip_executes(scale):
    settings = DialectSettings()
    source = esolangs.generate("Line", "01", scale=scale, settings=settings)
    raw = Raster.from_png(source.to_png())
    assert raw.settings is None
    restored = esolangs.load_program(
        "Line", esolangs.dump_program("Line", raw, settings=settings)
    )
    assert restored.rows == source.rows
    assert _evaluate("Line", restored, inputs=1) == "01"


@pytest.mark.parametrize("value", ["!", "abcd", "é"])
def test_invalid_png(value):
    document = json.loads(
        esolangs.dump_program("Line", esolangs.generate("Line", "01"))
    )
    document["source"] = value
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Line", json.dumps(document))


@pytest.mark.medium
def test_line_highlight_tracks_ink_after_crop_and_scale() -> None:
    from esolangs import generate
    from esolangs.raster import Raster

    source = generate("Line", "01", scale=3)
    assert isinstance(source, Raster)
    history = History("Line", Raster.from_png(source.to_png()), "1\n")
    for step in range(100):
        frame = history.at(step)
        if frame.halted:
            assert frame.output == "1"
            break
        assert _highlighted(render(frame)) == "#"
    else:
        pytest.fail("identity did not halt within 100 steps")


class TestTheSmallInconsistencies:
    """Each one was a place this CLI did not do what it does everywhere else."""

    def test_a_repeated_isolated_is_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Every value-taking option refused a repeat; this flag did not."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--isolated", "--isolated", "brainfuck", str(path)],
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
            patch.object(sys, "stdin", _FakeStdin("")),
        ):
            main()
        captured = capsysbinary.readouterr()
        assert b"no effect on Line" in captured.err
        image = esolangs.Raster.from_png(captured.out)
        assert esolangs.run("Line", image, stdin="0\n0\n") == "0"

    def test_a_breakpoint_that_never_fires_says_so(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It looked exactly like a program that never reached it."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        _out, err = call_both(
            [
                "debug",
                "--break-on-output",
                "Z",
                "--steps",
                "5000",
                "brainfuck",
                str(path),
            ],
            capsys,
            stdin="0\n1\n",
        )
        assert "no breakpoint matched" in err

    def test_a_breakpoint_that_fires_is_not_reported_as_missed(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The other half, so the note means something."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        out, err = call_both(
            [
                "debug",
                "--break-on-output",
                "1",
                "--steps",
                "5000",
                "brainfuck",
                str(path),
            ],
            capsys,
            stdin="01",
        )
        assert "stopped: breakpoint" in out
        assert "no breakpoint matched" not in err


def test_source_kind_cannot_change_language_contract():
    document = json.loads(
        esolangs.dump_program("Line", esolangs.generate("Line", "01"))
    )
    document["language"] = "brainfuck"
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Brainfuck", json.dumps(document))


@pytest.mark.medium
def test_raster_interpreter_retains_geometry_hint():
    image = Raster((((255, 255, 255),),))
    with pytest.raises(esolangs.ProgramError, match=r".+") as caught:
        esolangs.run("Line", image, scale=None, timeout=1)
    assert "dark connected paths" in caught.value.__notes__[0]


def test_line_detection_has_no_sixteen_fold_ceiling() -> None:
    # A small stroke with uneven outer margins retains its ink-anchored grid.
    mask = Mask(
        40,
        45,
        [0] * 3 + [((1 << 34) - 1) << 5] * 17 + [((1 << 17) - 1) << 5] * 17 + [0] * 3,
    )
    assert detect_scale(mask) == 17


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
    assert esolangs.run("Line", image, stdin="1\n", scale=2) == "0"
    assert esolangs.run("Line", Raster.from_png(image.to_png()), stdin="1\n") == "0"
    with pytest.raises(esolangs.ProgramError, match="uniform"):
        esolangs.run("Line", image, stdin="1\n", scale=3)


def test_it_reads_numeric_tokens_on_the_same_line() -> None:
    assert_reads_tokens_on_one_line("Line")
