"""What ``--timeout`` bounds, what it costs, and the code it exits with."""

import subprocess
import sys
import time
from pathlib import Path

import pytest

import esolangs
from esolangs import cli, cli_io
from esolangs.cli import HELP
from tests.cli.test_cli import _program, call_main
from tests.cli_support import _LOOPS, call_both
from tests.generator_support import evaluate_generated


# 3.0s over 12 tests: waits out a real timeout.
@pytest.mark.medium
class TestATimeoutIsNotAProgramError:
    """They shared exit 1, so a script could not tell them apart."""

    def test_a_program_failure_still_exits_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The other half of the distinction, which is what makes 124 useful."""
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "brainfuck", _program(tmp_path, ",")], capsys, stdin="")
        assert exc.value.code == 1

    def test_a_termination_languages_timeout_says_it_is_the_answer(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It read as a failure when it was the result."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 1])
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", _LOOPS, "123", _program(tmp_path, program)], capsys
            )
        assert exc.value.code == 124
        assert "this timeout is the answer 1" in capsys.readouterr().err


class TestATimeoutValueIsCheckedBeforeThePositionals:
    """A forgotten number blamed the argument that was not the problem."""

    @pytest.mark.parametrize("command", ["run", "debug"])
    def test_a_missing_number_names_the_timeout(
        self, command: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It reported `missing <program-file>`, having eaten the language."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main([command, "--timeout", "brainfuck", str(path)], capsys)
        assert exc.value.code == 2
        assert "--timeout must be a number" in capsys.readouterr().err

    @pytest.mark.parametrize("command", ["run", "debug"])
    def test_a_dash_leading_value_still_reaches_the_finiteness_check(
        self, command: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The earlier fix depended on option-before-stray order; still holds."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main([command, "--timeout", "-inf", "brainfuck", str(path)], capsys)
        assert exc.value.code == 2
        assert "must be finite" in capsys.readouterr().err


class TestTimeoutValuesAreCheckedOnce:
    """The CLI had its own rules and did not know about the library's."""

    @pytest.mark.parametrize("value", ["1e9", "1e10"])
    def test_a_huge_bound_is_refused_not_crashed(
        self, value: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """1e9 gave `ItimerError`, 1e10 an `OverflowError`, both raw."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", value, "brainfuck", str(path)],
                capsys,
                stdin="1\n0\n",
            )
        assert exc.value.code == 2
        assert "--timeout must be at most" in capsys.readouterr().err

    def test_a_tiny_bound_is_refused_by_the_same_rules(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The floor the library grew, which this used not to apply."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", "0.0001", "brainfuck", str(path)],
                capsys,
                stdin="1\n0\n",
            )
        assert exc.value.code == 2
        assert "--timeout must be at least" in capsys.readouterr().err

    @pytest.mark.parametrize("value", ["0", "abc", "inf", "nan"])
    def test_the_old_refusals_still_hold(
        self, value: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Delegating must not lose the cases that already worked."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", value, "brainfuck", str(path)],
                capsys,
                stdin="1\n0\n",
            )
        assert exc.value.code == 2
        assert "--timeout" in capsys.readouterr().err

    def test_a_reasonable_bound_is_accepted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Between the floor and the ceiling, nothing changes."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        out = call_main(
            ["run", "--timeout", "100000", "brainfuck", str(path)],
            capsys,
            stdin="10",
        )
        assert out.strip() == "1"


class TestRunCanBeBounded:
    """Several of these languages loop forever by design."""

    @pytest.mark.medium
    def test_timeout_stops_a_program_that_never_halts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", _LOOPS, "brainfuck", _program(tmp_path, "+[]")],
                capsys,
            )
        # 124, after timeout(1).  This was 1 -- the same code a program's
        # own failure exits with -- which left the four languages whose
        # answer *is* a timeout indistinguishable from a crash.
        assert exc.value.code == 124
        assert "timeout" in capsys.readouterr().err


class TestAnUnboundedRunSaysSo:
    """Several of these languages loop forever by design."""

    def test_a_bounded_run_never_arms_it(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With --timeout there is nothing to warn about."""
        monkeypatch.setattr(cli_io, "_UNBOUNDED_NOTICE_AFTER", 0.01)
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        _out, err = call_both(
            ["run", "--timeout", "10", "brainfuck", str(path)], capsys, stdin="1\n0\n"
        )
        assert "no bound" not in err

    def test_debug_warns_about_a_termination_language(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`run` gained this a round earlier and `debug` did not."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 0])
        path = tmp_path / "p.txt"
        path.write_text(program)
        _out, err = call_both(["debug", "123", str(path)], capsys)
        assert "not terminating" in err

    def test_a_bounded_debug_is_not_told_to_pass_a_bound(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--steps is a bound as much as --timeout is."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 1])
        path = tmp_path / "p.txt"
        path.write_text(program)
        _out, err = call_both(["debug", "--steps", "200", "123", str(path)], capsys)
        assert "pass --timeout" not in err


# waits out real stdin timeouts: drives the CLI as a subprocess.
@pytest.mark.medium
class TestStdinCannotHangTheCommandForever:
    """`run` read stdin to EOF before doing anything, and --timeout missed it."""

    def _run_with_open_stdin(self, args: list[str], wait: float) -> tuple[int, str]:
        """Start the CLI with stdin held open and never written."""
        proc = subprocess.Popen(
            [sys.executable, "-m", "esolangs", *args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            proc.wait(timeout=wait)
        except subprocess.TimeoutExpired:
            proc.kill()
            return -1, ""
        finally:
            if proc.stdin:
                proc.stdin.close()
        return proc.returncode, proc.stderr.read() if proc.stderr else ""

    @pytest.mark.slow
    def test_a_timeout_bounds_the_read(self, tmp_path: Path) -> None:
        """It bounded execution only, and the block happens before that."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        code, err = self._run_with_open_stdin(
            ["run", "--timeout", "2", "brainfuck", str(path)], 20
        )
        assert code == 124
        assert "no input arrived on stdin" in err

    @pytest.mark.slow
    def test_an_unknown_language_is_named_without_reading_stdin(
        self, tmp_path: Path
    ) -> None:
        """It blocked forever before saying the one thing it already knew."""
        path = tmp_path / "p.txt"
        path.write_text("+.")
        code, err = self._run_with_open_stdin(
            ["run", "--timeout", "30", "NotALang", str(path)], 20
        )
        assert code == 2
        assert "unknown language" in err

    @pytest.mark.slow
    def test_a_language_that_reads_no_stdin_is_told_so(self, tmp_path: Path) -> None:
        """RAM0 embeds its inputs, so the wait was for input nobody wanted."""
        path = tmp_path / "p.txt"
        path.write_text(
            esolangs.instantiate("RAM0", esolangs.generate("RAM0", "0110"), [0, 1])
        )
        code, err = self._run_with_open_stdin(
            ["run", "--timeout", "2", "RAM0", str(path)], 20
        )
        assert code == 124
        assert "read no stdin" in err


class TestEvaluationProvesRatherThanWaits:
    """A generous bound must not be paid per diverging row."""

    @pytest.mark.parametrize("language", ["123", "ArrowQueue"])
    def test_a_diverging_row_is_settled_quickly(self, language: str) -> None:
        """A generous bound must not be paid; it is the backstop, not the clock."""
        start = time.perf_counter()
        answer = evaluate_generated(language, "0110", timeout=20)
        elapsed = time.perf_counter() - start
        assert answer == "0110"
        assert elapsed < 20, f"{language} waited {elapsed:.1f}s out of a 20s bound"


class TestAnInterruptIsNotATraceback:
    """The tool invites Ctrl-C and then tracebacked when it arrived."""

    def test_it_exits_130_with_one_line(
        self, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """130 is the shell's convention for a command killed by SIGINT."""

        def _interrupt() -> None:
            raise KeyboardInterrupt

        monkeypatch.setattr(cli, "_dispatch", _interrupt)
        with pytest.raises(SystemExit) as exc:
            cli.main()
        assert exc.value.code == 130
        assert capsys.readouterr().err.strip() == "interrupted"


class TestTheDocumentedExitCodesAreTheRealOnes:
    """``run --help`` said a program error exits 1.  A malformed one exits 2."""

    @pytest.mark.parametrize(
        ("label", "source", "stdin", "expected"),
        [
            ("ran", "+++.", "", 0),
            ("read past the end", ",.", "", 1),
            ("malformed program", "[[[", "", 2),
        ],
    )
    def test_each_code_is_what_the_help_claims(
        self,
        label: str,
        source: str,
        stdin: str,
        expected: int,
        capsys: pytest.CaptureFixture[str],
        tmp_path: Path,
    ) -> None:
        """Measured through ``main``, which is what a script sees."""
        path = tmp_path / "p.bf"
        path.write_text(source)
        args = ["run", "--timeout", "5", "brainfuck", str(path)]
        if expected == 0:
            call_both(args, capsys, stdin=stdin)
            return
        with pytest.raises(SystemExit) as exit_code:
            call_main(args, capsys, stdin=stdin)
        assert exit_code.value.code == expected, label

    def test_an_unreadable_ask_is_two(
        self, capsys: pytest.CaptureFixture[str], tmp_path: Path
    ) -> None:
        """An unknown language and a missing file are both the ask, not the run."""
        for args in (
            ["run", "--timeout", "5", "nosuchlang", str(tmp_path / "p.bf")],
            ["run", "--timeout", "5", "brainfuck", str(tmp_path / "absent.bf")],
        ):
            with pytest.raises(SystemExit) as exit_code:
                call_main(args, capsys)
            assert exit_code.value.code == 2, args

    def test_the_help_lists_them(self) -> None:
        """The claim has to be in the text a reader is pointed at."""
        text = HELP["run"]
        for code in ("0 ran", "124", "130"):
            assert code in text
        assert "distinct from a program error's 1" not in text


class TestDebugMirrorsRunsExitCodes:
    """It exited 0 for a clean halt, a timeout and a crash alike."""

    def test_a_raise_exits_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The program failed, which is `run`'s exit 1."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        with pytest.raises(SystemExit) as exc:
            call_main(["debug", "brainfuck", str(path)], capsys, stdin="")
        assert exc.value.code == 1

    @pytest.mark.medium
    def test_a_timeout_exits_124(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Matching `run`, and distinct from the program having broken."""
        path = tmp_path / "p.txt"
        path.write_text("+[]")
        with pytest.raises(SystemExit) as exc:
            call_main(["debug", "--timeout", _LOOPS, "brainfuck", str(path)], capsys)
        assert exc.value.code == 124


@pytest.mark.medium
@pytest.mark.parametrize(
    ("source", "options", "code", "output", "error"),
    [
        (",.", [], 0, "A", ""),
        (",[.]", ["--max-output", "3"], 1, "AAA\n", "output limit exceeded"),
        (",[.]", ["--max-output", "0"], 1, "", "output limit exceeded"),
        # Includes worker startup; 0.5s lost output in two full-suite runs.
        (",.+[]", ["--timeout", "2"], 124, "A\n", "deadline"),
        (",.", [], 0, "1", ""),
    ],
)
def test_isolated_cli_retains_output_and_verdict(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    source: str,
    options: list[str],
    code: int,
    output: str,
    error: str,
) -> None:
    path = tmp_path / "program.txt"
    path.write_text(source)
    args = ["run", "--isolated", *options, "brainfuck", str(path)]
    stdin = "1" if output == "1" else "A"
    if code:
        with pytest.raises(SystemExit, match=f"^{code}$"):
            call_both(args, capsys, stdin)
        captured = capsys.readouterr()
        out, err = captured.out, captured.err
    else:
        out, err = call_both(args, capsys, stdin)
    assert out == output
    assert error in err


@pytest.mark.medium
@pytest.mark.parametrize(
    "options",
    [
        ["--max-output", "1"],
        ["--isolated", "--max-output", "-1"],
        ["--isolated", "--max-output", "abc"],
        ["--isolated", "--isolated"],
        ["--isolated", "--max-output", "1", "--max-output", "2"],
    ],
)
def test_isolated_options_fail_before_file_or_stdin_reads(
    options: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit, match=r"^2$"):
        call_both(["run", *options, "brainfuck", "missing"], capsys)
    assert "cannot read" not in capsys.readouterr().err
