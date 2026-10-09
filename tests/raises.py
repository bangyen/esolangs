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


def assert_rejected_with_hint(language: str, source: str, hint: str) -> None:
    """Malformed ``source`` is refused at load with a repair ``hint`` attached."""
    import esolangs  # the installed package: a mutation bundle copies this file

    with pytest.raises(ValueError, match=r".+") as caught:
        # Rejection is at load (ms); the bound only stops a hang, and 0.2s
        # tripped on a contended release runner.
        esolangs.run(language, source, timeout=2)
    assert any(hint in note for note in caught.value.__notes__)
