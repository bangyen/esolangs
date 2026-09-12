r"""A ``pytest.raises`` that pins the whole message, not a substring."""

import contextlib
from collections.abc import Iterator

import pytest


@contextlib.contextmanager
def raises_message(
    exc_type: type[BaseException],
    message: str,
    detail: object = None,
) -> Iterator[pytest.ExceptionInfo[BaseException]]:
    r"""Assert the block raises ``exc_type`` with exactly ``message``."""
    with pytest.raises(exc_type) as caught:
        yield caught
    assert str(caught.value) == message, detail
