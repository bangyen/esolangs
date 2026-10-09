"""Bounded and portable execution paths."""

from concurrent.futures import ThreadPoolExecutor

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
