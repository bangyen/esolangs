"""What ``--execution-timeout`` bounds, what it costs, and the code it exits with."""

import subprocess
import sys
import time
from importlib import import_module
from pathlib import Path
from threading import Event

import pytest

import esolangs
from esolangs import cli
from esolangs.cli.help import help_text
from tests.support.cli_support import _LOOPS, _program, _refused, call_both, call_main
from tests.support.generator_support import evaluate_generated
from tests.support.pick import languages
from tests.support.reference import REFERENCE

_BAD_TIMEOUTS = [
    # A forgotten number blamed the positional it had swallowed.
    ("--execution-timeout brainfuck", "--execution-timeout must be a number"),
    ("--execution-timeout -inf brainfuck", "must be finite"),
    # 1e10 overflowed the source read's thread wait as a raw OverflowError.
    ("--execution-timeout 1e9 brainfuck", "--execution-timeout must be at most"),
    ("--execution-timeout 1e10 brainfuck", "--execution-timeout must be at most"),
    *[
        (f"--execution-timeout {v} brainfuck", "--execution-timeout")
        for v in ("0", "abc", "inf", "nan")
    ],
]


@pytest.mark.parametrize(("args", "message"), _BAD_TIMEOUTS)
def test_a_bad_timeout_is_refused_with_exit_2(args, message, tmp_path, capsys) -> None:
    refused = _refused(f"run {args} prog:,.", tmp_path, capsys, "1\n")
    assert message in refused


def test_file_and_stdin_share_the_acquisition_budget(
    tmp_path, capsys, monkeypatch
) -> None:
    run_cli = import_module("esolangs.cli.run")
    now = 100.0
    read_program = run_cli._read_program

    def read_file(path, timeout, **options):
        nonlocal now
        assert timeout == 5
        now += 2
        return read_program(path, timeout, **options)

    def read_stdin(timeout, _hint, **_options):
        nonlocal now
        assert timeout == 3
        now += 1
        return ""

    def execute(_language, _program, *, limits, **_options):
        assert limits == esolangs.ExecutionLimits(
            execution_timeout=5,
            total_timeout=7,
            preparation_timeout=3,
        )
        return esolangs.run(REFERENCE, "+.")

    monkeypatch.setattr(run_cli, "monotonic", lambda: now)
    monkeypatch.setattr(run_cli, "_read_program", read_file)
    monkeypatch.setattr(run_cli, "_read_stdin", read_stdin)
    monkeypatch.setattr(run_cli, "run", execute)
    assert (
        call_main(
            [
                "run",
                "--total-timeout",
                "10",
                "--preparation-timeout",
                "6",
                "--execution-timeout",
                "5",
                REFERENCE,
                _program(tmp_path, "+."),
            ],
            capsys,
        )
        == "\x01"
    )


@pytest.mark.parametrize("flag", ["--total-timeout", "--preparation-timeout"])
def test_shortest_deadline_applies_to_blocked_stdin(
    flag, tmp_path, capsys, monkeypatch
) -> None:
    from esolangs.cli import io

    release = Event()

    def blocked():
        release.wait(2)
        return ""

    def read_stdin(*args, **kwargs):
        monkeypatch.setattr(io.sys.stdin, "read", blocked)
        return io._read_stdin(*args, **kwargs)

    monkeypatch.setattr("esolangs.cli.run._read_stdin", read_stdin)
    try:
        with pytest.raises(SystemExit, match=r"^124$"):
            call_main(
                [
                    "run",
                    flag,
                    "0.1",
                    "--execution-timeout",
                    "1",
                    REFERENCE,
                    _program(tmp_path, "+."),
                ],
                capsys,
            )
        assert f"({flag})" in capsys.readouterr().err
    finally:
        release.set()


@pytest.mark.medium
def test_blocked_stdin_pipe_exits_without_aborting(tmp_path: Path) -> None:
    cmd = [
        sys.executable,
        "-m",
        "esolangs",
        "run",
        "--preparation-timeout",
        "0.2",
        REFERENCE,
        _program(tmp_path, ",."),
    ]
    with subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as child:
        try:
            # Keep the writer open through the child's shutdown.
            assert child.wait(timeout=10) == 124
        finally:
            if child.poll() is None:
                child.kill()
        assert child.stderr is not None
        diagnostic = child.stderr.read()
    assert b"--preparation-timeout" in diagnostic
    assert b"Fatal Python error" not in diagnostic


def test_preparation_deadline_applies_to_decoding(
    tmp_path, capsys, monkeypatch
) -> None:
    release = Event()

    def decode(*_args, **_kwargs):
        release.wait(2)
        raise AssertionError("decoding should have timed out")

    monkeypatch.setattr("esolangs.cli.io._check_program", decode)
    try:
        with pytest.raises(SystemExit, match=r"^124$"):
            call_main(
                [
                    "run",
                    "--preparation-timeout",
                    "0.2",
                    REFERENCE,
                    _program(tmp_path, "+."),
                ],
                capsys,
            )
        assert "decoding" in capsys.readouterr().err
    finally:
        release.set()


class TestTimeoutValuesAreCheckedOnce:
    """The CLI had its own rules and did not know about the library's."""

    def test_a_reasonable_bound_is_accepted(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Between the floor and the ceiling, nothing changes."""
        path = tmp_path / "p.txt"
        esolangs.to_file(REFERENCE, esolangs.generate(REFERENCE, "0110"), path)
        out = call_main(
            ["run", "--execution-timeout", "100000", REFERENCE, str(path)],
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
                [
                    "run",
                    "--execution-timeout",
                    _LOOPS,
                    REFERENCE,
                    _program(tmp_path, "+[]"),
                ],
                capsys,
            )
        # 124, after timeout(1).  This was 1 -- the same code a program's
        # own failure exits with -- which left the four languages whose
        # answer *is* a timeout indistinguishable from a crash.
        assert exc.value.code == 124
        assert "timeout" in capsys.readouterr().err


class TestEvaluationProvesRatherThanWaits:
    """A generous bound must not be paid per diverging row."""

    @pytest.mark.parametrize(
        "language", languages(answer_mode="termination", boolean_generator=True)[:2]
    )
    def test_a_diverging_row_is_settled_quickly(self, language: str) -> None:
        """A generous bound must not be paid; it is the backstop, not the clock."""
        start = time.perf_counter()
        answer = evaluate_generated(language, "0110", timeout=20)
        elapsed = time.perf_counter() - start
        assert answer == "0110"
        assert elapsed < 20, f"{language} waited {elapsed:.1f}s out of a 20s bound"


def test_run_states_no_boolean_verdict(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """run takes any program; the halt/diverge contract is a generated one's."""
    language = languages(answer_mode="termination", boolean_generator=True)[0]
    facts = esolangs.describe(language)
    bits = ["--bits", "1"] if facts.parameterized else []
    source, _ = call_both(["generate", *bits, language, "00"], capsys)
    path = tmp_path / "zero.txt"
    path.write_text(source)
    stdin = esolangs.encode_inputs(language, [1]) if facts.reads_input else ""
    _, error = call_both(
        ["run", "--execution-timeout", "20", language, str(path)], capsys, stdin
    )
    assert "answer" not in error.lower()
    assert "termination" not in error.lower()


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
        args = ["run", "--execution-timeout", "5", REFERENCE, str(path)]
        if expected == 0:
            call_both(args, capsys, stdin=stdin)
            return
        with pytest.raises(SystemExit) as exit_code:
            call_main(args, capsys, stdin=stdin)
        assert exit_code.value.code == expected, label

    def test_the_help_lists_them(self) -> None:
        """The claim has to be in the text a reader is pointed at."""
        text = help_text("run")
        for code in ("0 ran", "124", "130"):
            assert code in text
        assert "distinct from a program error's 1" not in text


@pytest.mark.medium
@pytest.mark.parametrize(
    ("source", "options", "code", "output", "error"),
    [
        (",.", [], 0, "A", ""),
        (",[.]", ["--max-output", "3"], 124, "AAA", "output limit exceeded"),
        (",[.]", ["--max-output", "0"], 124, "", "output limit exceeded"),
        # Includes worker startup; 0.5s lost output in two full-suite runs.
        (",.+[]", ["--execution-timeout", "2"], 124, "A", "2.0-second timeout"),
        (",.+[]", ["--total-timeout", "2"], 124, "A", "--total-timeout"),
        (",.", ["--preparation-timeout", "20"], 0, "A", ""),
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
    args = ["run", "--isolated", *options, REFERENCE, str(path)]
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
        ["--max-output", "-1"],
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
        call_both(["run", *options, REFERENCE, "missing"], capsys)
    assert "cannot read" not in capsys.readouterr().err
