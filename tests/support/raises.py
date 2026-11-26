"""A ``pytest.raises`` that pins the whole message, not a substring."""

import contextlib
from collections.abc import Iterator

import pytest

import esolangs


@contextlib.contextmanager
def raises_message(
    exc_type: type[BaseException],
    message: str,
    detail: object = None,
) -> Iterator[pytest.ExceptionInfo[BaseException]]:
    """Assert the block raises ``exc_type`` with exactly ``message``."""
    with pytest.raises(exc_type) as caught:
        yield caught
    assert str(caught.value) == message, detail


def assert_rejected_with_hint(
    language: str,
    source: object,
    hint: str,
    *,
    message: str = "",
    error: type[Exception] | None = None,
    stdin: str = "",
    **options: object,
) -> None:
    """Running ``source`` raises ``error`` (a ``ProgramError`` by default)
    with a repair ``hint`` attached."""

    with pytest.raises(error or esolangs.ProgramError, match=r".+") as caught:
        # Rejection is at load or within a few steps (ms); the bound only
        # stops a hang, and 0.2s tripped on a contended release runner.
        esolangs.run(
            language,
            source,
            stdin=stdin,
            limits=esolangs.ExecutionLimits(execution_timeout=2),
            **options,
        ).unwrap()
    assert message in str(caught.value)
    assert any(hint in note for note in caught.value.__notes__)


def assert_halts_with_hint(
    language: str, source: str, message: str, hint: str, stdin: str = ""
) -> None:
    """Running ``source`` halts with ``message`` and a repair ``hint``."""
    from esolangs.exceptions import HaltError

    assert_rejected_with_hint(
        language, source, hint, message=message, error=HaltError, stdin=stdin
    )


def assert_numeric_token_replayed(name, source, valid, output):
    """Retry the same numeric instruction and compare its error evidence."""
    api = esolangs.Language(name)
    dbg = api.make_debugger(source, stdin="oops " + valid)
    limit = esolangs.ExecutionLimits(max_steps=16)
    with pytest.raises(esolangs.ProgramError) as first:
        dbg.run(limits=limit)
    boundary = dbg.snapshot()
    assert first.value.observation.input_position == 4
    assert first.value.observation.input_reads == 1
    with pytest.raises(esolangs.ProgramError) as again:
        dbg.run(limits=limit)
    assert again.value is not first.value
    assert str(again.value) == str(first.value)
    assert again.value.observation == first.value.observation
    assert again.value.__notes__ == first.value.__notes__
    assert dbg.snapshot() == boundary
    assert api.run(source, stdin=valid, limits=limit).unwrap().output == output
