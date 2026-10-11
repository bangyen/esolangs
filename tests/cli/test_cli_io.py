"""Reading a program and stdin, and writing what came back."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs.cli import main
from esolangs.cli_io import (
    _bounded_read,
)
from tests.cli.test_cli import call_main, run_cli
from tests.support.cli_support import EXAMPLES
from tests.support.pick import languages, one_where

#: A language whose input bits are not spelled 0 and 1, if one is registered.
_SPELLED = one_where(
    lambda d: d["input_encoding"] != ("0", "1"), boolean_generator=True
)


class TestTheStdinReaderInProcess:
    """The subprocess tests prove the behaviour; these reach the lines."""

    @pytest.mark.parametrize("command", ["run", "debug"])
    def test_an_unknown_language_is_named_before_stdin_is_read(
        self, command: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It read stdin first, so this answer waited on input forever."""
        path = tmp_path / "p.txt"
        path.write_text("+.")

        class _NeverEnding:
            def isatty(self) -> bool:
                return False

            def read(self) -> str:  # pragma: no cover - must not be called
                raise AssertionError("stdin was read before the name resolved")

        argv = ["esolangs", command, "NotALang", str(path)]
        with (
            patch.object(sys, "stdin", _NeverEnding()),
            patch.object(sys, "argv", argv),
            pytest.raises(SystemExit) as exc,
        ):
            main()
        assert exc.value.code == 2
        assert "unknown language" in capsys.readouterr().err


# 6.0s over 12 tests: drives the CLI as a subprocess.
@pytest.mark.medium
class TestNonTextInputIsRefusedNotCrashed:
    """Pointing `run` at a PNG dumped a traceback with internal paths in it."""

    def test_a_binary_program_file_is_refused(self, tmp_path: Path) -> None:
        """Reachable by a newcomer pointing `run` at the wrong file."""
        path = tmp_path / "binary.txt"
        path.write_bytes(bytes(range(256)))
        result = run_cli("run", "brainfuck", str(path))
        assert result.returncode == 2
        assert "not text" in result.stderr
        assert "Traceback" not in result.stderr

    def test_debug_refuses_it_too(self, tmp_path: Path) -> None:
        """The same reader serves both commands."""
        path = tmp_path / "binary.txt"
        path.write_bytes(bytes(range(256)))
        result = run_cli("debug", "--steps", "5", "brainfuck", str(path))
        assert result.returncode == 2
        assert "not text" in result.stderr

    def test_binary_stdin_is_refused(self) -> None:
        """A program's binary output piped into `read-answer`."""
        result = subprocess.run(
            [sys.executable, "-m", "esolangs", "read-answer", "brainfuck"],
            input=b"\x80\x81",
            capture_output=True,
            timeout=60,
            check=False,
        )
        assert result.returncode == 2
        assert b"not text" in result.stderr
        assert b"Traceback" not in result.stderr

    def test_binary_stdin_is_refused_under_utf8_mode(self) -> None:
        """The same pipe on a runner whose locale is ``C``."""
        env = {**os.environ, "PYTHONUTF8": "1"}
        result = subprocess.run(
            [sys.executable, "-m", "esolangs", "read-answer", "brainfuck"],
            input=b"\x80\x81",
            capture_output=True,
            timeout=60,
            check=False,
            env=env,
        )
        assert result.returncode == 2
        assert b"not text" in result.stderr
        assert b"Traceback" not in result.stderr

    def test_the_library_names_it_as_a_program_error(self, tmp_path: Path) -> None:
        """``check_program`` decodes a Path and had the same gap."""
        path = tmp_path / "binary.txt"
        path.write_bytes(bytes(range(256)))
        with pytest.raises(esolangs.ProgramError, match="not text"):
            esolangs.run("brainfuck", path)


# 8.5s over 9 tests: drives the CLI as a subprocess.
@pytest.mark.medium
class TestReadingTheProgramFileIsBounded:
    """It was the one unguarded blocking call left in the command."""

    def test_a_character_device_is_refused_by_size(self) -> None:
        """`/dev/zero` reached 3.9 GB of resident memory and never returned."""
        result = run_cli("run", "--timeout", "2", "brainfuck", "/dev/zero")
        assert result.returncode == 2
        assert "larger than" in result.stderr

    @pytest.mark.slow
    def test_a_fifo_with_no_writer_is_bounded(self, tmp_path: Path) -> None:
        """`--timeout` bounds the *run*, and this happens before one."""
        import os

        fifo = tmp_path / "fifo"
        os.mkfifo(fifo)
        result = run_cli("run", "--timeout", "2", "brainfuck", str(fifo))
        assert result.returncode == 124
        assert "not delivering data" in result.stderr

    def test_an_ordinary_program_still_reads(self, tmp_path: Path) -> None:
        """The guard is worth nothing if it costs the normal path."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        result = run_cli("run", "brainfuck", str(path), stdin="10")
        assert result.returncode == 0
        assert result.stdout.strip() == "1"


class TestTheBoundedReaderInProcess:
    """The subprocess tests prove the behaviour; these reach the lines."""

    @pytest.mark.parametrize("prefix", [b"", b"aa"])
    def test_oversized_utf8_is_refused_before_decoding(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], prefix: bytes
    ) -> None:
        """Both a split character and a valid truncated prefix exceed the cap."""
        path = tmp_path / "large.txt"
        path.write_bytes(prefix + ("€" * 600_000).encode())
        with pytest.raises(SystemExit) as exc:
            _bounded_read(str(path), 1.0)
        assert exc.value.code == 2
        assert "larger than" in capsys.readouterr().err

    def test_oversized_png_is_refused_before_decoding(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The image branch must obey the same byte cap as text."""
        from esolangs.cli_io import _MAX_PROGRAM_BYTES
        from esolangs.raster import Raster

        path = tmp_path / "large.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"x" * _MAX_PROGRAM_BYTES)
        with (
            patch.object(Raster, "from_png") as decode,
            pytest.raises(SystemExit) as exc,
        ):
            _bounded_read(str(path), 1.0)
        assert exc.value.code == 2
        assert "larger than" in capsys.readouterr().err
        decode.assert_not_called()

    def test_exact_byte_cap_is_accepted(self, tmp_path: Path) -> None:
        """The sentinel byte distinguishes an oversized file from a full one."""
        from esolangs.cli_io import _MAX_PROGRAM_BYTES

        text = "é" * (_MAX_PROGRAM_BYTES // 2)
        path = tmp_path / "full.txt"
        path.write_bytes(text.encode())
        assert _bounded_read(str(path), 1.0) == text.encode()


# 2.2s over 6 tests: drives the CLI as a subprocess.
@pytest.mark.medium
class TestAClosedPipeIsNotAnError:
    """`esolangs generate ... | head` is an ordinary thing to type."""

    def test_closing_before_the_first_write_is_silent(self) -> None:
        """It printed "Exception ignored while flushing sys.stdout"."""
        import subprocess

        first = subprocess.Popen(
            [sys.executable, "-m", "esolangs", "generate", "brainfuck", "0110"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert first.stdout is not None
        first.stdout.close()
        first.wait(timeout=30)
        assert first.stderr is not None
        assert "BrokenPipeError" not in first.stderr.read()


class TestProgramFilesLoad:
    """The newline a text file ends with is the file's, not the program's."""

    @pytest.mark.parametrize("spelled", _SPELLED)
    def test_a_generated_file_runs_as_written(
        self, spelled: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``esolangs generate > f`` wrote a newline three interpreters reject."""
        path = tmp_path / "g.txt"
        path.write_text(esolangs.generate(spelled, "0110") + "\n")
        stdin = esolangs.encode_inputs(spelled, [0, 1])
        assert call_main(["run", spelled, str(path)], capsys, stdin=stdin) == "1"

    @pytest.mark.parametrize(
        "name",
        [
            name
            for name in languages(
                source_kind="text", parameterized=False, answer_mode="output"
            )
            if esolangs.describe(name)["examples"]
        ],
    )
    def test_the_committed_examples_run(
        self, name: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Three once failed on the newline their own file ends with."""
        path = EXAMPLES.parent / esolangs.describe(name)["examples"][0]
        stdin = esolangs.encode_inputs(name, [0, 1])
        assert call_main(["run", name, str(path)], capsys, stdin=stdin)


@pytest.mark.parametrize("filename", ["--timeout", "--help"])
def test_run_flag_filename_after_separator(
    filename: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A positional filename must survive every option parser."""
    monkeypatch.chdir(tmp_path)
    Path(filename).write_text("+.")
    assert call_main(["run", "brainfuck", "--", filename], capsys) == "\x01"


def test_debug_tui_filename_after_separator(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The debugger's bare flag is positional after the separator."""
    monkeypatch.chdir(tmp_path)
    Path("--tui").write_text("+.")
    assert "\\x01" in call_main(["debug", "brainfuck", "--", "--tui"], capsys)


@pytest.mark.parametrize(
    ("command", "filename"), [("list", "--json"), ("describe", "--spec")]
)
def test_bare_flags_after_separator_are_positional(
    command: str,
    filename: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The separator must not silently enable a display mode."""
    with (
        patch.object(sys, "argv", ["esolangs", command, "--", filename]),
        pytest.raises(SystemExit) as exc,
    ):
        main()
    assert exc.value.code == 2
    assert not capsys.readouterr().out


def test_width_after_separator_is_positional() -> None:
    from esolangs.cli_args import _pop_width

    assert _pop_width(["--", "--width", "80"]) == (["--", "--width", "80"], None, False)
