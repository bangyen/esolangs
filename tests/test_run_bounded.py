"""Portable cooperative execution preserves output and distinguishes exhaustion."""

from concurrent.futures import ThreadPoolExecutor

import pytest

import esolangs
from tests.samples import NEVER_SELF_HALTS, NONDETERMINISTIC_AGAINST_RUN, SAMPLES

pytestmark = pytest.mark.medium


@pytest.mark.parametrize(
    "language", sorted(set(SAMPLES) - NEVER_SELF_HALTS - NONDETERMINISTIC_AGAINST_RUN)
)
def test_bounded_run_matches_whole_program_execution(language: str) -> None:
    program, stdin = SAMPLES[language]
    assert esolangs.run_bounded(
        language, program, stdin, max_steps=100_000
    ) == esolangs.run(language, program, stdin)


def test_bounded_run_executes_generated_xor() -> None:
    program = esolangs.generate("Fargo", "0110")
    for row, expected in enumerate("0110"):
        stdin = esolangs.encode_inputs("Fargo", tuple(map(int, format(row, "02b"))))
        assert esolangs.run_bounded("Fargo", program, stdin, max_steps=1000) == expected


def test_step_exhaustion_keeps_partial_output() -> None:
    with pytest.raises(esolangs.ExecutionTimeoutError, match="max_steps") as caught:
        esolangs.run_bounded("brainfuck", "+.[]", max_steps=10)
    assert caught.value.partial_output == "\x01"


def test_timeout_works_on_a_worker_thread() -> None:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(esolangs.run_bounded, "brainfuck", "+[]", timeout=0.01)
        with pytest.raises(esolangs.ExecutionTimeoutError, match="timeout"):
            future.result(timeout=5)


def test_time_and_step_bounds_allow_a_halt() -> None:
    assert esolangs.run_bounded("brainfuck", "+.", timeout=1, max_steps=2) == "\x01"
    assert esolangs.run_bounded("brainfuck", "", max_steps=0) == ""


@pytest.mark.parametrize(
    "options", [{}, {"max_steps": -1}, {"max_steps": True}, {"timeout": 0}]
)
def test_invalid_bounds_are_refused(options: dict[str, object]) -> None:
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run_bounded("brainfuck", "", **options)


def test_raster_execution_is_refused() -> None:
    with pytest.raises(esolangs.ArgumentError, match="no step machine"):
        esolangs.run_bounded("Line", "", max_steps=1)


def test_interpreter_errors_are_preserved() -> None:
    with pytest.raises(esolangs.InputExhaustedError):
        esolangs.run_bounded("brainfuck", ",", max_steps=1)


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
        esolangs.run_bounded(language, program, max_steps=100)
    assert caught.value.partial_output == output
