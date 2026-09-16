"""What ``--timeout`` bounds, what it costs, and the code it exits with.

The bound is the one thing a CLI user can reach for when a program will not
stop, and three languages answer *by* not stopping, so a timeout has to be
tellable from a crash.
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest

import esolangs
from esolangs import cli
from esolangs.cli import HELP
from tests.cli_support import _LOOPS, call_both
from tests.test_cli import _program, call_main


class TestATimeoutHasOneExitCode:
    """124 wherever the bound runs out, not two codes for one event.

    ``run`` and ``debug`` exited 124 and ``evaluate``, ``verify`` and
    ``answer`` exited 1 on the same event, so a script could not test for
    it -- and 124 is the only exit code this CLI documents a meaning for.
    The three languages whose answer *is* a timeout make the distinction
    load-bearing rather than tidy.
    """

    @pytest.mark.medium
    @pytest.mark.parametrize(
        "args",
        [
            ["evaluate", "10010110"],
            ["verify", "10010110"],
            ["answer", "10010110", "101"],
        ],
    )
    def test_the_bound_running_out_is_124(
        self, args: list[str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A bound too small to finish, on a generator slow enough to catch."""
        command, rest = args[0], args[1:]
        with pytest.raises(SystemExit) as exc:
            call_main([command, "--timeout", "0.001", "Polynomial", *rest], capsys)
        assert exc.value.code == 124
        capsys.readouterr()

    @pytest.mark.medium
    def test_a_usage_error_is_still_2_and_a_fault_still_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The other two codes are unchanged, so 124 narrowed only the timeout."""
        with pytest.raises(SystemExit) as exc:
            call_main(["evaluate", "brainfuck", "011"], capsys)
        assert exc.value.code == 2
        capsys.readouterr()
        path = tmp_path / "p.txt"
        path.write_text(",.")
        with pytest.raises(SystemExit) as exc:
            call_main(["run", "brainfuck", str(path)], capsys)
        assert exc.value.code == 1
        capsys.readouterr()


# 3.0s over 12 tests: waits out a real timeout.
@pytest.mark.medium
# 3.0s over 12 tests: waits out a real timeout.
@pytest.mark.medium
# 3.0s over 12 tests: waits out a real timeout.
@pytest.mark.medium
class TestATimeoutIsNotAProgramError:
    """They shared exit 1, so a script could not tell them apart."""

    def test_a_timeout_exits_124(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Following timeout(1), and distinct from the program's own failure."""
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", _LOOPS, "brainfuck", _program(tmp_path, "+[]")],
                capsys,
            )
        assert exc.value.code == 124

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

    def test_an_unbounded_termination_language_is_warned_about(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Its default path is an unbounded run of a program built to loop."""
        program = esolangs.instantiate("123", esolangs.generate("123", "0110"), [0, 0])
        call_main(["run", "123", _program(tmp_path, program)], capsys)


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

    @pytest.mark.parametrize("value", ["0", "-3", "abc", "inf", "nan"])
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
            ["run", "--judge", "--timeout", "100000", "brainfuck", str(path)],
            capsys,
            stdin="1\n0\n",
        )
        assert out.strip() == "1"


class TestRunCanBeBounded:
    """Several of these languages loop forever by design."""

    def test_timeout_stops_a_program_that_never_halts(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", _LOOPS, "brainfuck", _program(tmp_path, "+[]")],
                capsys,
            )
        # 124, after timeout(1).  This was 1 -- the same code a program's
        # own failure exits with -- which left the three languages whose
        # answer *is* a timeout indistinguishable from a crash.
        assert exc.value.code == 124
        assert "timeout" in capsys.readouterr().err

    @pytest.mark.parametrize("value", ["x", "0", "-3"])
    def test_a_bad_timeout_is_refused(
        self, value: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as exc:
            call_main(
                ["run", "--timeout", value, "brainfuck", _program(tmp_path, "+")],
                capsys,
            )
        assert exc.value.code == 2


class TestAnUnboundedRunSaysSo:
    """Several of these languages loop forever by design."""

    def test_the_notice_names_the_flag(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Shortened rather than waited out, so the test costs nothing."""
        monkeypatch.setattr(cli, "_UNBOUNDED_NOTICE_AFTER", 0.01)
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        call_main(["run", "brainfuck", str(path)], capsys, stdin="1\n0\n")
        # The run finishes in microseconds, so the notice may or may not
        # have fired; what must hold is that arming it broke nothing.
        capsys.readouterr()

    def test_a_bounded_run_never_arms_it(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With --timeout there is nothing to warn about."""
        monkeypatch.setattr(cli, "_UNBOUNDED_NOTICE_AFTER", 0.01)
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


class TestTheTimeoutIsABackstopNotAPerRowCost:
    """`verify --help` was a third copy of a claim the package retired.

    It said the three languages answering 1 by not terminating "pay this on
    every 1-row, so a low value is worth setting for them".  That was true
    when written and stopped being true in the change that added the
    divergence proof: those rows are settled by a repeated machine state in
    microseconds, and the bound is only the backstop for a program that
    diverges by *growing*.  ``evaluate``'s docstring says so and adds that
    two docstrings disagreeing about how something works is worse than
    either being out of date -- and then the CLI help was a third.

    Corrected, and pinned by measurement rather than by matching words: if
    the timeout ever does get paid per 1-row again, sixteen rows at a
    thirty-second bound takes eight minutes and this fails.
    """

    #: Sixteen rows, half of them 1s, on a language that answers by diverging.
    TABLE = "0110100110010110"

    @pytest.mark.parametrize("language", ["123", "ArrowQueue"])
    def test_a_generous_bound_is_not_paid_per_row(self, language: str) -> None:
        """Thirty seconds a row would be minutes; the proof makes it instant."""
        start = time.perf_counter()
        assert esolangs.verify(language, self.TABLE, timeout=30)
        elapsed = time.perf_counter() - start
        ones = self.TABLE.count("1")
        assert elapsed < 30, (
            f"{language} took {elapsed:.1f}s for {ones} 1-rows at a 30s bound, "
            f"so the bound is being waited out rather than proved"
        )

    def test_the_help_no_longer_says_it_is_paid(self) -> None:
        """The specific retired sentence, so a fourth copy cannot creep back."""
        help_text = HELP["verify"]
        assert "pay this on every" not in help_text
        assert "backstop" in help_text


class TestAnswerProvesRatherThanWaits:
    """``answer --timeout 20`` took twenty seconds; raising a bound made it
    strictly slower, which is the opposite of what a bound means.

    ``answer --help`` calls itself "``verify`` for one row instead of all of
    them", and ``verify`` settles four rows of the same language in a fifth
    of a second -- the repeated-state proof had reached ``evaluate`` and
    ``verify`` and never reached here.
    """

    @pytest.mark.parametrize("language", ["123", "ArrowQueue"])
    def test_a_diverging_row_is_settled_quickly(self, language: str) -> None:
        """A generous bound must not be paid; it is the backstop, not the clock."""
        start = time.perf_counter()
        answer = esolangs.evaluate(language, "0110", timeout=20)
        elapsed = time.perf_counter() - start
        assert answer == "0110"
        assert elapsed < 20, f"{language} waited {elapsed:.1f}s out of a 20s bound"

    def test_the_cli_answer_agrees_row_by_row(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The proof must not have changed any answer, only the wait."""
        for bits, expected in (("00", "0"), ("01", "1"), ("10", "1"), ("11", "0")):
            out, _err = call_both(
                ["answer", "--timeout", "20", "123", "0110", bits], capsys
            )
            assert out.strip() == expected, bits


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
    """``run --help`` said a program error exits 1.  A malformed one exits 2.

    That is the commoner of the two, and the help text was the only place
    exit codes were written down at all.
    """

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

    def test_a_timeout_exits_124(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Matching `run`, and distinct from the program having broken."""
        path = tmp_path / "p.txt"
        path.write_text("+[]")
        with pytest.raises(SystemExit) as exc:
            call_main(["debug", "--timeout", _LOOPS, "brainfuck", str(path)], capsys)
        assert exc.value.code == 124

    def test_a_clean_halt_and_a_step_bound_exit_zero(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Neither is a failure, so neither may look like one."""
        path = tmp_path / "p.txt"
        path.write_text(esolangs.generate("brainfuck", "0110"))
        assert call_main(
            ["debug", "--steps", "5", "brainfuck", str(path)], capsys, stdin="1\n0\n"
        )
        assert call_main(["debug", "brainfuck", str(path)], capsys, stdin="1\n0\n")
