"""Bounded and portable execution paths."""

from concurrent.futures import ThreadPoolExecutor

import pytest

import esolangs
from tests.support.pick import languages
from tests.support.reference import REFERENCE
from tests.support.samples import SAMPLES

pytestmark = pytest.mark.medium


# ``max_steps`` is one driver for every language: a tape and a grid one.
@pytest.mark.parametrize(
    "language",
    [
        next(n for n in languages(state_model=model, self_halts=True) if n in SAMPLES)
        for model in ("tape", "grid")
    ],
)
def test_bounded_run_matches_whole_program_execution(language: str) -> None:
    program, stdin = SAMPLES[language]
    assert (
        esolangs.run(language, program, stdin=stdin, max_steps=100_000).output
        == esolangs.run(language, program, stdin=stdin).output
    )


def test_step_exhaustion_keeps_partial_output() -> None:
    for isolated in (False, True):
        with pytest.raises(esolangs.ExecutionTimeoutError, match="max_steps") as caught:
            esolangs.run(REFERENCE, "+.[]", max_steps=10, isolated=isolated)
        assert caught.value.partial_output == "\x01"
        assert caught.value.bound == "max_steps"


def test_timeout_works_on_a_worker_thread() -> None:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            esolangs.run, REFERENCE, "+[]", max_steps=1_000_000, timeout=0.01
        )
        with pytest.raises(esolangs.ExecutionTimeoutError, match="timeout"):
            future.result(timeout=5)


def test_time_and_step_bounds_allow_a_halt() -> None:
    for isolated in (False, True):
        options = {"max_output": 1} if isolated else {}
        assert (
            esolangs.run(
                REFERENCE, "+.", timeout=1, max_steps=2, isolated=isolated, **options
            ).output
            == "\x01"
        )
        assert esolangs.run(REFERENCE, "", max_steps=0, isolated=isolated).output == ""
        assert (
            esolangs.run(REFERENCE, "+.", max_steps=10**5000, isolated=isolated).output
            == "\x01"
        )


@pytest.mark.parametrize(
    "options", [{"max_steps": -1}, {"max_steps": True}, {"timeout": 0}]
)
def test_invalid_bounds_are_refused(options: dict[str, object]) -> None:
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run(REFERENCE, "", **options)


@pytest.mark.parametrize(
    "language", languages(source_kind="raster", boolean_generator=True)
)
def test_raster_execution_obeys_the_step_bound(language: str) -> None:
    source = esolangs.generate(language, "01")
    stdin = esolangs.encode_inputs(language, [1])
    out = esolangs.run(language, source, stdin=stdin, max_steps=1000).output
    assert esolangs.read_answer(language, out) == "1"
    with pytest.raises(esolangs.ExecutionTimeoutError):
        esolangs.run(language, source, stdin=stdin, max_steps=0)


def test_interpreter_errors_are_preserved() -> None:
    with pytest.raises(esolangs.InputExhaustedError):
        esolangs.run(REFERENCE, ",", max_steps=1)


def test_a_program_error_echoing_the_digit_cap_text_stays_a_program_error() -> None:
    """Malformed source reading "Exceeds the limit (" is not a host limit."""
    from esolangs.runtime._execution import interpreter_errors

    with pytest.raises(esolangs.ProgramError) as caught, interpreter_errors("deep"):
        raise ValueError("invalid expression: Exceeds the limit (")
    assert not isinstance(caught.value, esolangs.InterpreterLimitError)

    from esolangs.results import ExecutionResult
    from esolangs.runtime.io import ScriptedIO

    def normalize_twice(wrapped, supplied, port, normalized):
        with interpreter_errors("outer loading"):
            try:
                with interpreter_errors(
                    "inner loading", None if supplied is not None else port
                ):
                    try:
                        raise ValueError(
                            "Exceeds the limit (4300 digits) "
                            "for integer string conversion"
                        )
                    except ValueError as digit_error:
                        if wrapped:
                            error = esolangs.ProgramError("wrapped digit cap")
                            if supplied is not None:
                                error.partial_output = port.getvalue()
                                error.observation = supplied
                            raise error from digit_error
                        raise
            except esolangs.InterpreterLimitError as error:
                normalized.append(error)
                raise

    for wrapped, reported in ((False, False), (True, False), (True, True)):
        port = ScriptedIO()
        port.print_str("A")
        supplied = (
            ExecutionResult(port.getvalue(), port.position(), port.reads, port.past_end)
            if reported
            else None
        )
        normalized = []
        with pytest.raises(esolangs.InterpreterLimitError) as limited:
            normalize_twice(wrapped, supplied, port, normalized)
        assert type(limited.value) is esolangs.InterpreterLimitError
        assert limited.value is normalized[0]
        assert limited.value.partial_output == "A"
        assert limited.value.observation == ExecutionResult("A", 0, 0, 0)
        if reported:
            assert limited.value.observation is supplied


def test_worker_budgets_validate_before_acquisition_and_keep_output_limits():
    class Unread:
        def read(self, *_args):
            pytest.fail("invalid budgets must be refused before acquisition")

    for max_steps in (-1, True, 1.5):
        with pytest.raises(esolangs.ArgumentError, match="max_steps"):
            esolangs.run(
                REFERENCE, "+.", stdin=Unread(), isolated=True, max_steps=max_steps
            )
    with pytest.raises(esolangs.InterpreterLimitError, match="output limit") as caught:
        esolangs.run(
            REFERENCE, "+..", isolated=True, timeout=5, max_steps=3, max_output=1
        )
    assert caught.value.partial_output == "\x01"
    with pytest.raises(esolangs.InputExhaustedError) as exhausted:
        esolangs.run(REFERENCE, "+.,", isolated=True, max_steps=3)
    assert exhausted.value.partial_output == "\x01"
