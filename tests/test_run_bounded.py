"""Bounded and portable execution paths."""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import esolangs
from tests.samples import SAMPLES

pytestmark = pytest.mark.medium


# ``max_steps`` is one driver for every language: a tape and a grid one.
@pytest.mark.parametrize("language", ["Smallfuck", "Befunge"])
def test_bounded_run_matches_whole_program_execution(language: str) -> None:
    program, stdin = SAMPLES[language]
    assert esolangs.run(
        language, program, stdin=stdin, max_steps=100_000
    ) == esolangs.run(language, program, stdin=stdin)


def test_bounded_run_executes_generated_xor() -> None:
    program = esolangs.generate("Fargo", "0110")
    for row, expected in enumerate("0110"):
        stdin = esolangs.encode_inputs("Fargo", tuple(map(int, format(row, "02b"))))
        assert esolangs.run("Fargo", program, stdin=stdin, max_steps=1000) == expected


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
    assert esolangs.run(language, source, stdin="1\n", max_steps=1000) == "1"
    with pytest.raises(esolangs.ExecutionTimeoutError):
        esolangs.run(language, source, stdin="1\n", max_steps=0)


def test_interpreter_errors_are_preserved() -> None:
    with pytest.raises(esolangs.InputExhaustedError):
        esolangs.run("brainfuck", ",", max_steps=1)


def test_worker_thread_loads_unicode_path(tmp_path: Path) -> None:
    source = tmp_path / "λ program.sophie"
    source.write_text("#λ,", encoding="utf-8")
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(
            esolangs.run, "Sophie", source, isolated=True, max_output=1
        )
        assert result.result(timeout=10) == "λ"


@pytest.mark.parametrize(
    ("language", "source", "options", "code", "output", "diagnostic"),
    [
        ("Sophie", "#λ,", [], 0, "λ", ""),
        ("Sophie", "#λ,,", ["--max-output", "1"], 1, "λ\n", "output limit"),
        # Sophie's ';' reads 0 at EOF, so the input error comes from brainfuck.
        ("brainfuck", ",", [], 1, "", "input"),
        ("Sophie", ";.", [], 0, "0", ""),
    ],
)
def test_cli_unicode_path_and_error(
    tmp_path: Path,
    language: str,
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
            language,
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
