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
from tests.cli_support import EXAMPLES, call_both
from tests.stdin_check import _check_stdin
from tests.test_cli import call_main, run_cli


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


# 2.0s over 21 tests: drives the CLI as a subprocess.
@pytest.mark.medium
# 2.0s over 21 tests: drives the CLI as a subprocess.
@pytest.mark.medium
# 2.0s over 21 tests: drives the CLI as a subprocess.
@pytest.mark.medium
class TestOutputSurvivesAFailure:
    """A run that failed emitted nothing at all, and it had the bytes."""

    PRINTS_THEN_FAILS = '[PSH STR "Hi"][PRT STR][PRT STR][POP][END]'
    LOOPS_PRINTING = "[PSH INT 9][PRT INT][JMP B 2][END]"

    def test_a_halt_carries_what_was_printed(self) -> None:
        """The attribute, which is what the CLI reads."""
        with pytest.raises(esolangs.HaltError) as caught:
            esolangs.run("Modulous", self.PRINTS_THEN_FAILS, "")
        assert caught.value.partial_output == "Hi"

    def test_it_is_in_the_traceback_too(self) -> None:
        """The note, for anyone who only sees the traceback."""
        with pytest.raises(esolangs.HaltError) as caught:
            esolangs.run("Modulous", self.PRINTS_THEN_FAILS, "")
        assert "printed 'Hi'" in "\n".join(getattr(caught.value, "__notes__", []))

    def test_a_timeout_carries_it(self) -> None:
        """The case that matters most: a loop you meant to be finite."""
        with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
            esolangs.run("Modulous", self.LOOPS_PRINTING, "", 0.01)
        assert caught.value.partial_output.startswith("999")

    def test_an_error_before_the_run_carries_nothing(self) -> None:
        """Empty is the honest answer when the program never started."""
        with pytest.raises(esolangs.UnknownLanguageError) as unknown:
            esolangs.run("nosuchlang", "+", "")
        assert unknown.value.partial_output == ""
        with pytest.raises(esolangs.ProgramError) as bad:
            esolangs.run("brainfuck", "[[[", "")
        assert bad.value.partial_output == ""

    def test_a_successful_run_is_unchanged(self) -> None:
        """The attribute is for failures; success returns as it always did."""
        assert esolangs.run("brainfuck", "+++.", "") == "\x03"

    def test_the_cli_prints_it_before_the_error(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """On stdout, where a successful run puts it, so a pipe sees the same."""
        path = tmp_path / "m.txt"
        path.write_text(self.PRINTS_THEN_FAILS)
        with pytest.raises(SystemExit) as exit_code:
            call_main(["run", "--timeout", "5", "Modulous", str(path)], capsys)
        captured = capsys.readouterr()
        assert captured.out.startswith("Hi")
        assert "stack is empty" in captured.err
        assert exit_code.value.code == 1

    def test_the_cli_says_nothing_extra_when_there_was_nothing(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """A program that printed nothing must not gain a blank line."""
        path = tmp_path / "m.txt"
        path.write_text("[POP][END]")
        with pytest.raises(SystemExit):
            call_main(["run", "--timeout", "5", "Modulous", str(path)], capsys)
        assert capsys.readouterr().out == ""


class TestStdinIsCheckedAgainstTheDeclaredAlphabet:
    """`encode` refused these bytes all along; `run` answered them."""

    @pytest.mark.parametrize("line", [" 1", "\t1", "2", "true", "01", "+1"])
    def test_plain_run_accepts_a_non_boolean_line(
        self, line: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """General execution does not impose a Boolean input alphabet."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0101"))
        _out, err = call_both(
            ["run", "brainfuck", str(path)], capsys, stdin=f"0\n{line}\n"
        )
        assert "spells its bits" not in err

    def test_a_correct_encoding_is_silent_and_right(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Doing it right must stay quiet, or the check is noise."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0101"))
        out, err = call_both(["run", "brainfuck", str(path)], capsys, stdin="01")
        assert out.strip() == "1"
        assert err == ""

    def test_the_alphabet_check_reads_the_declared_alphabet(self) -> None:
        """Grapheme's own bits are %/A, so 0/1 is what is wrong there."""
        _check_stdin("Grapheme", "%\nA\n")
        # 0/1 is wrong *here*, and the specific message is the one that
        # fires: the general stray-line rule runs last so a language with
        # something better to say keeps saying it.
        with pytest.raises(esolangs.ArgumentError, match="spells its bits"):
            _check_stdin("Grapheme", "0\n1\n")


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

    def test_a_generated_file_runs_as_written(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``esolangs generate > f`` wrote a newline three interpreters reject."""
        path = tmp_path / "g.txt"
        path.write_text(esolangs.generate("Grapheme", "0110") + "\n")
        assert call_main(["run", "Grapheme", str(path)], capsys, stdin="%\nA\n") == "1"

    @pytest.mark.parametrize(
        ("stem", "name"),
        [("cvnc", "CV(N)(C)"), ("grapheme", "Grapheme"), ("nocomment", "NoComment")],
    )
    def test_the_committed_examples_run(
        self, stem: str, name: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """All three failed on the newline their own file ends with."""
        zero, one = esolangs.describe(name)["input_encoding"]  # type: ignore[misc]
        out = call_main(
            ["run", name, str(EXAMPLES / f"{stem}.txt")],
            capsys,
            stdin=f"{zero}\n{one}\n",
        )
        assert out


class TestPrivateStdinCheckSaysWhatItCanActuallyCheck:
    """Its help listed "the wrong number of lines" among what it catches
    without a table.  For most languages it cannot.
    """

    def test_a_line_per_bit_language_accepts_any_count(self) -> None:
        """Not a bug -- a count needs an arity, and only a table has one."""
        for stdin in ("", "1", "101"):
            _check_stdin("brainfuck", stdin)

    def test_the_table_is_what_catches_the_count(self) -> None:
        """The other half of the claim: with one, the count is checked."""
        with pytest.raises(esolangs.ArgumentError):
            _check_stdin("brainfuck", "1\n0\n1\n", "0110")

    def test_a_one_line_language_does_catch_a_stray_line(self) -> None:
        """Which is why the help can still claim a shape check at all."""
        with pytest.raises(esolangs.ArgumentError, match="unexpected character"):
            _check_stdin("Clockwise", "1\n0\n")


@pytest.mark.parametrize("filename", ["--timeout", "--judge", "--help", "--version"])
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


@pytest.mark.medium
@pytest.mark.parametrize(
    ("arguments", "diagnostic"),
    [
        (["--table", "xyz", "brainfuck"], "unknown option"),
        (["--judge", "123"], "unknown option"),
    ],
)
def test_run_rejects_bad_options_before_acquiring_source_or_stdin(
    arguments, diagnostic, monkeypatch, capsys
):
    import esolangs.cli_run as cli_run

    def unreadable(*_args, **_kwargs):
        pytest.fail("invalid run options must be rejected before reading")

    monkeypatch.setattr(cli_run, "_read_program", unreadable)
    monkeypatch.setattr(cli_run, "_read_stdin", unreadable)
    with pytest.raises(SystemExit) as caught:
        call_main(["run", *arguments, "never-read.txt"], capsys)
    assert caught.value.code == 2
    assert diagnostic in capsys.readouterr().err
