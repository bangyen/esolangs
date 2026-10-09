"""A ``pytest.raises`` that pins the whole message, not a substring."""

import contextlib
from collections.abc import Iterator

import pytest


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
    error: type[Exception] = ValueError,
    stdin: str = "",
    **options: object,
) -> None:
    """Running ``source`` raises ``error`` with a repair ``hint`` attached."""
    import esolangs  # the installed package: a mutation bundle copies this file

    with pytest.raises(error, match=r".+") as caught:
        # Rejection is at load or within a few steps (ms); the bound only
        # stops a hang, and 0.2s tripped on a contended release runner.
        esolangs.run(language, source, stdin=stdin, timeout=2, **options)  # type: ignore[arg-type]
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
