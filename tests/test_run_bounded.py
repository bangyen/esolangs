"""Bounded and portable execution paths."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import esolangs
from tests.samples import NEVER_SELF_HALTS, NONDETERMINISTIC_AGAINST_RUN, SAMPLES

pytestmark = pytest.mark.medium


@pytest.mark.parametrize(
    "language", sorted(set(SAMPLES) - NEVER_SELF_HALTS - NONDETERMINISTIC_AGAINST_RUN)
)
def test_bounded_run_matches_whole_program_execution(language: str) -> None:
    program, stdin = SAMPLES[language]
    assert esolangs.run(language, program, stdin, max_steps=100_000) == esolangs.run(
        language, program, stdin
    )


def test_bounded_run_executes_generated_xor() -> None:
    program = esolangs.generate("Fargo", "0110")
    for row, expected in enumerate("0110"):
        stdin = esolangs.encode_inputs("Fargo", tuple(map(int, format(row, "02b"))))
        assert esolangs.run("Fargo", program, stdin, max_steps=1000) == expected


def test_step_exhaustion_keeps_partial_output() -> None:
    with pytest.raises(esolangs.ExecutionTimeoutError, match="max_steps") as caught:
        esolangs.run("brainfuck", "+.[]", max_steps=10)
    assert caught.value.partial_output == "\x01"


def test_timeout_works_on_a_worker_thread() -> None:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            esolangs.run, "brainfuck", "+[]", max_steps=1_000_000, timeout=0.01
        )
        with pytest.raises(esolangs.ExecutionTimeoutError, match="timeout"):
            future.result(timeout=5)


def test_time_and_step_bounds_allow_a_halt() -> None:
    assert esolangs.run("brainfuck", "+.", timeout=1, max_steps=2) == "\x01"
    assert esolangs.run("brainfuck", "", max_steps=0) == ""


@pytest.mark.parametrize(
    "options", [{"max_steps": -1}, {"max_steps": True}, {"timeout": 0}]
)
def test_invalid_bounds_are_refused(options: dict[str, object]) -> None:
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run("brainfuck", "", **options)


@pytest.mark.parametrize("language", ["Line", "Piet"])
def test_raster_execution_obeys_the_step_bound(language: str) -> None:
    source = esolangs.generate(language, "01")
    assert esolangs.run(language, source, "1\n", max_steps=1000) == "1"
    with pytest.raises(esolangs.ExecutionTimeoutError):
        esolangs.run(language, source, "1\n", max_steps=0)


def test_interpreter_errors_are_preserved() -> None:
    with pytest.raises(esolangs.InputExhaustedError):
        esolangs.run("brainfuck", ",", max_steps=1)


@pytest.mark.parametrize(
    ("language", "program", "error", "output"),
    [
        ("brainfuck", "+.,", esolangs.InputExhaustedError, "\x01"),
        ("Underload", "(A)S!", esolangs.HaltError, "A"),
        (
            "Algebraic Programming Language",
            "65\n" + "(" * 90,
            esolangs.InterpreterLimitError,
            "65\n",
        ),
    ],
)
def test_interpreter_errors_keep_prior_output(
    language: str, program: str, error: type[esolangs.EsolangError], output: str
) -> None:
    with pytest.raises(error) as caught:
        esolangs.run(language, program, max_steps=100)
    assert caught.value.partial_output == output


def test_worker_thread_loads_unicode_path(tmp_path: Path) -> None:
    source = tmp_path / "λ program.sophie"
    source.write_text("#λ,", encoding="utf-8")
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(
            esolangs.run, "Sophie", source, isolated=True, max_output=1
        )
        assert result.result(timeout=10) == "λ"


@pytest.mark.parametrize(
    ("source", "options", "code", "output", "diagnostic"),
    [
        ("#λ,", [], 0, "λ", ""),
        ("#λ,,", ["--max-output", "1"], 1, "λ\n", "output limit"),
        (";", [], 1, "", "input"),
    ],
)
def test_cli_unicode_path_and_error(
    tmp_path: Path,
    source: str,
    options: list[str],
    code: int,
    output: str,
    diagnostic: str,
) -> None:
    path = tmp_path / "λ program.sophie"
    path.write_text(source, encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "esolangs",
            "run",
            "--isolated",
            *options,
            "Sophie",
            str(path),
        ],
        input="",
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=False,
    )
    assert result.returncode == code
    assert result.stdout == output
    assert diagnostic in result.stderr.lower()
