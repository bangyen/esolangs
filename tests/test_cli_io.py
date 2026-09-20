"""Reading a program and stdin, and writing what came back.

Both ends are untrusted: a program file can be a fifo, a terabyte or bytes
that are not text, and the answer can be a code point Python will not encode.
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import esolangs
from esolangs import cli
from esolangs.cli import HELP, main
from tests.cli_support import EXAMPLES, call_both
from tests.test_cli import call_main, run_cli


class TestTheDecodeGuardsInProcess:
    """The subprocess tests above prove the behaviour; these reach the lines.

    Coverage is measured in this process, so a path exercised only through
    ``run_cli`` is invisible to it -- which would leave the handlers that
    fix this round's one real bug looking untested.
    """

    def test_read_program_refuses_a_binary_file(self, tmp_path: Path) -> None:
        """The file reader's own clause, called directly."""
        path = tmp_path / "b.txt"
        path.write_bytes(bytes(range(256)))
        with pytest.raises(SystemExit) as exc:
            cli._read_program(str(path))  # noqa: SLF001
        assert exc.value.code == 2

    def test_read_program_still_refuses_an_unreadable_path(
        self, tmp_path: Path
    ) -> None:
        """The OSError clause beside it, which the new one must not shadow."""
        with pytest.raises(SystemExit) as exc:
            cli._read_program(str(tmp_path))  # noqa: SLF001
        assert exc.value.code == 2

    def test_read_stdin_refuses_undecodable_bytes(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A stdin whose read raises, as a piped binary stream's does."""

        class _BadStdin:
            def isatty(self) -> bool:
                return False

            def read(self) -> str:
                raise UnicodeDecodeError("utf-8", b"\x80", 0, 1, "invalid start byte")

        with patch.object(sys, "stdin", _BadStdin()), pytest.raises(SystemExit) as exc:
            cli._read_stdin()  # noqa: SLF001
        assert exc.value.code == 2
        assert "not text" in capsys.readouterr().err

    def test_read_stdin_refuses_bytes_a_lenient_stream_let_through(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The same stdin under UTF-8 mode, where the read does not raise.

        Python turns UTF-8 mode on by itself under a ``C`` locale, and it
        decodes the standard streams with ``surrogateescape``.  So the
        clause above never fired on CI: the bytes arrived as surrogates and
        reached a reader, which reported them as a bad *answer*.  The
        message and the offset must match the strict-mode refusal.
        """

        class _LenientStdin:
            def isatty(self) -> bool:
                return False

            def read(self) -> str:
                return "\udc80\udc81"

        with (
            patch.object(sys, "stdin", _LenientStdin()),
            pytest.raises(SystemExit) as exc,
        ):
            cli._read_stdin()  # noqa: SLF001
        assert exc.value.code == 2
        assert "not text (invalid UTF-8 at byte 0)" in capsys.readouterr().err

    def test_read_stdin_keeps_text_a_lenient_stream_decoded(self) -> None:
        """The check must not cost a well-formed stdin its characters."""

        class _WideStdin:
            def isatty(self) -> bool:
                return False

            def read(self) -> str:
                return "é\N{ROCKET}1\n"

        with patch.object(sys, "stdin", _WideStdin()):
            assert cli._read_stdin() == "é\N{ROCKET}1\n"  # noqa: SLF001

    def test_read_stdin_is_empty_on_a_terminal(self) -> None:
        """The branch beside it: nothing piped in."""

        class _Tty:
            def isatty(self) -> bool:
                return True

            def read(self) -> str:  # pragma: no cover - never called
                raise AssertionError("should not read a terminal")

        with patch.object(sys, "stdin", _Tty()):
            assert cli._read_stdin() == ""  # noqa: SLF001

    def test_the_unbounded_notice_writes_one_line(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Called directly rather than waited for."""
        cli._UnboundedNotice._say("run")  # noqa: SLF001
        err = capsys.readouterr().err
        assert "no bound" in err
        assert "--timeout" in err

    def test_debug_warns_about_a_mismatched_shape_too(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`run` and `debug` feed the same stdin to the same interpreter."""
        path = tmp_path / "g.txt"
        path.write_text(esolangs.generate("Grapheme", "0110"))
        _out, err = call_both(
            ["debug", "--steps", "50", "Grapheme", str(path)], capsys, stdin="1\n0\n"
        )
        assert "spells its bits" in err


class TestTheStdinReaderInProcess:
    """The subprocess tests prove the behaviour; these reach the lines."""

    def test_a_read_that_never_finishes_is_bounded(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A stdin whose read blocks, as an open-but-silent pipe does."""
        import threading

        blocked = threading.Event()

        class _BlockingStdin:
            def isatty(self) -> bool:
                return False

            def read(self) -> str:
                blocked.wait(30)
                return ""

        with (
            patch.object(sys, "stdin", _BlockingStdin()),
            pytest.raises(SystemExit) as exc,
        ):
            cli._read_stdin(0.2)  # noqa: SLF001
        blocked.set()
        assert exc.value.code == 124
        assert "no input arrived on stdin" in capsys.readouterr().err

    def test_an_unexpected_read_error_is_not_swallowed(self) -> None:
        """Only a decode error is turned into a message; the rest propagate."""

        class _BrokenStdin:
            def isatty(self) -> bool:
                return False

            def read(self) -> str:
                raise RuntimeError("disk on fire")

        with (
            patch.object(sys, "stdin", _BrokenStdin()),
            pytest.raises(RuntimeError, match="disk on fire"),
        ):
            cli._read_stdin()  # noqa: SLF001

    def test_the_waiting_notice_writes_one_line(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Called directly rather than waited for."""
        cli._WaitingNotice._say("; close it")  # noqa: SLF001
        err = capsys.readouterr().err
        assert "still waiting for input on stdin" in err
        assert "close it" in err

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
    """Pointing `run` at a PNG dumped a traceback with internal paths in it.

    ``UnicodeDecodeError`` is a ``ValueError``, not an ``OSError``, so the
    handler that turns "Is a directory" into one clean line never saw it.
    Four call sites decode -- two files and two stdins -- and all four had
    the same hole, so all four are pinned here.
    """

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
        """The same pipe on a runner whose locale is ``C``.

        The test above passes only where the standard streams decode
        strictly.  CI's do not -- Python enables UTF-8 mode under a ``C``
        locale, which decodes stdin with ``surrogateescape`` -- and this
        refusal reached a reader there instead, for one release.  Setting
        the flag reproduces that runner anywhere.
        """
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
    """A run that failed emitted nothing at all, and it had the bytes.

    A Modulous program that prints ``Hi`` and then pops an empty stack gave
    an empty stdout, an empty stderr and exit 1, while ``debug`` on the same
    file showed ``output: 'Hi'``.  When the program is one you are still
    writing, what it printed before it broke is most of the diagnosis.
    """

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
    """`encode` refused these bytes all along; `run` answered them.

    A leading space, a tab, a `2` or the word `true` each produced a
    confident wrong bit at exit 0 -- and brainfuck and Sophie returned
    *different* answers for the same junk byte, which is what proved nothing
    was reading it.
    """

    @pytest.mark.parametrize("line", [" 1", "\t1", "2", "true", "01", "+1"])
    def test_plain_run_warns_about_a_stray_line(
        self, line: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A warning, because `run` executes arbitrary programs."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0101"))
        _out, err = call_both(
            ["run", "brainfuck", str(path)], capsys, stdin=f"0\n{line}\n"
        )
        assert "spells its bits" in err

    @pytest.mark.parametrize("line", [" 1", "2", "true"])
    def test_judge_refuses_it(
        self, line: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--judge asks for an answer bit, so a bad encoding is a usage error."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0101"))
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--judge", "brainfuck", str(path)], capsys, stdin=f"0\n{line}\n"
            )
        assert exc.value.code == 2
        assert "spells its bits" in capsys.readouterr().err

    def test_a_correct_encoding_is_silent_and_right(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Doing it right must stay quiet, or the check is noise."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0101"))
        out, err = call_both(
            ["run", "--judge", "brainfuck", str(path)], capsys, stdin="0\n1\n"
        )
        assert out.strip() == "1"
        assert err == ""

    def test_every_language_accepts_its_own_encoding(self) -> None:
        """The check must not fire on what `encode_inputs` itself produces."""
        noisy = []
        for name in esolangs.list_languages():
            if not esolangs.describe(name)["boolean_generator"]:
                continue
            if esolangs.describe(name)["parameterized"]:
                continue
            stdin = esolangs.encode_inputs(name, [1, 0], "0110")
            if cli._shape_warning(esolangs.describe(name), stdin):  # noqa: SLF001
                noisy.append(name)
        assert not noisy, noisy

    def test_the_alphabet_check_reads_the_declared_alphabet(self) -> None:
        """Grapheme's own bits are %/A, so 0/1 is what is wrong there."""
        facts = esolangs.describe("Grapheme")
        assert cli._shape_warning(facts, "%\nA\n") == ""  # noqa: SLF001
        # 0/1 is wrong *here*, and the specific message is the one that
        # fires: the general stray-line rule runs last so a language with
        # something better to say keeps saying it.
        assert "spells its bits" in cli._shape_warning(facts, "0\n1\n")  # noqa: SLF001


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
        """`--timeout` bounds the *run*, and this happens before one.

        The open blocks as well as the read -- a FIFO waits for a writer --
        so bounding only the read left it hanging one line earlier.
        """
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
        result = run_cli("run", "--judge", "brainfuck", str(path), stdin="1\n0\n")
        assert result.returncode == 0
        assert result.stdout.strip() == "1"


class TestTheBoundedReaderInProcess:
    """The subprocess tests prove the behaviour; these reach the lines."""

    def test_a_read_that_never_delivers_is_bounded(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A FIFO with no writer, as an open that never returns."""
        import os

        fifo = tmp_path / "fifo"
        os.mkfifo(fifo)
        with pytest.raises(SystemExit) as exc:
            cli._bounded_read(str(fifo), 0.2)  # noqa: SLF001
        assert exc.value.code == 124
        assert "not delivering data" in capsys.readouterr().err

    def test_an_unreadable_file_is_named(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The OSError clause, now that the open happens on the thread."""
        with pytest.raises(SystemExit) as exc:
            cli._bounded_read(str(tmp_path), 1.0)  # noqa: SLF001
        assert exc.value.code == 2
        assert "cannot read" in capsys.readouterr().err

    def test_a_binary_file_is_named(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """And the decode clause beside it."""
        path = tmp_path / "b.txt"
        path.write_bytes(bytes(range(256)))
        with pytest.raises(SystemExit) as exc:
            cli._bounded_read(str(path), 1.0)  # noqa: SLF001
        assert exc.value.code == 2
        assert "not text" in capsys.readouterr().err

    def test_an_unexpected_error_propagates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only the two named kinds become messages; the rest are bugs."""
        path = tmp_path / "p.txt"
        path.write_text("+.")

        def _boom(*_a: object, **_k: object) -> object:
            raise RuntimeError("disk on fire")

        monkeypatch.setattr("builtins.open", _boom)
        with pytest.raises(RuntimeError, match="disk on fire"):
            cli._bounded_read(str(path), 1.0)  # noqa: SLF001


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


class TestCheckStdinIsASubcommand:
    """The judge, usable without spending a run."""

    def test_it_accepts_a_correct_encoding(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Silence and exit 0."""
        out, err = call_both(
            ["check-stdin", "Grapheme"],
            capsys,
            stdin=esolangs.encode_inputs("Grapheme", [1, 0]),
        )
        assert out == ""
        assert err == ""

    def test_it_refuses_a_wrong_count_with_a_table(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The arity check, reachable without running a program."""
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["check-stdin", "--table", "0110", "brainfuck"],
                capsys,
                stdin="1\n0\n1\n",
            )
        assert exc.value.code == 2
        assert "reads 2 line(s)" in capsys.readouterr().err

    def test_it_reports_an_unknown_language_before_reading(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Resolved first, so a bad name does not wait on input either."""
        with pytest.raises(SystemExit) as exc:
            call_main(["check-stdin", "NotALang"], capsys, stdin="1\n")
        assert exc.value.code == 2
        assert "unknown language" in capsys.readouterr().err

    def test_it_is_suggested_on_a_typo(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The new command has to be in the set the did-you-mean searches."""
        with pytest.raises(SystemExit) as exc:
            call_main(["check-stdn", "brainfuck"], capsys)
        assert exc.value.code == 2
        assert "did you mean check-stdin" in capsys.readouterr().err


class TestCheckStdinSaysWhatItCanActuallyCheck:
    """Its help listed "the wrong number of lines" among what it catches
    without ``--table``.  For most languages it cannot.

    Without a table it judges *shape*, and for a line-per-bit language a
    shape is not a count: one line, three lines and none at all are
    equally well formed.  An empty stdin passing ``check-stdin brainfuck``
    is the trap, and the help now names it.
    """

    def test_a_line_per_bit_language_accepts_any_count(self) -> None:
        """Not a bug -- a count needs an arity, and only ``--table`` has one."""
        for stdin in ("", "1\n", "1\n0\n1\n"):
            esolangs.check_stdin("brainfuck", stdin)

    def test_the_table_is_what_catches_the_count(self) -> None:
        """The other half of the claim: with one, the count is checked."""
        with pytest.raises(esolangs.ArgumentError):
            esolangs.check_stdin("brainfuck", "1\n0\n1\n", "0110")

    def test_the_two_shape_languages_are_the_two_named(self) -> None:
        """The help names Clockwise and Fargo, so the data must agree.

        The first draft said "three languages want every bit on one line",
        which was wrong -- one does.  Counted here rather than believed.
        """
        shapes = {
            name: str(esolangs.describe(name)["input_shape"])
            for name in esolangs.list_languages()
            if esolangs.describe(name)["boolean_generator"]
        }
        assert [n for n, s in shapes.items() if s == "one_line"] == ["Clockwise"]
        assert [n for n, s in shapes.items() if s == "row_index"] == ["Fargo"]
        assert sum(s == "line_per_bit" for s in shapes.values()) == 60

    def test_a_one_line_language_does_catch_a_stray_line(self) -> None:
        """Which is why the help can still claim a shape check at all."""
        with pytest.raises(esolangs.ArgumentError, match="one line"):
            esolangs.check_stdin("Clockwise", "1\n0\n")

    def test_the_help_no_longer_overstates(self) -> None:
        """The retired phrase, so it cannot come back."""
        text = " ".join(HELP["check-stdin"].split())
        assert "the wrong number of lines" not in text
        assert "only --table knows how many bits the program wanted" in text
