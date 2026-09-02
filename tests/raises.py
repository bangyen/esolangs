"""A ``pytest.raises`` that pins the whole message, not a substring.

``pytest.raises(match=...)`` is a :func:`re.search`, so it passes on any
message *containing* the pattern: a rejection test written with
``match="unmatched"`` still passes when the position number is wrong, when
the quoted token is wrong, or when a different check fired than the one the
test names.  Several tests here say so in their own docstrings and assert
``str(caught.value) == message`` after the block instead, which is exact.

Anchoring the pattern is not the fix.  These messages carry regex
metacharacters -- ``unmatched '[' at position 4`` is an unterminated
character set, and ``not two-wide at (0, 1)`` reads the parentheses as a
group -- so ``match=f"^{message}$"`` raises :exc:`re.PatternError` on the
first and silently fails to match the second.  It needs :func:`re.escape`
around every message, and the escaped pattern is what pytest prints back on
a mismatch.

:func:`raises_message` keeps the exact comparison and the plain string diff
that comes with it, while spelling the check once.  Because it takes the
exception type as an argument, ruff's PT011 -- which fires on a *literal*
broad exception, and is what asks for ``match=`` in the first place -- stays
on for the rest of the suite, where it now flags a bare
``pytest.raises(ValueError)`` and points at this helper.
"""

import contextlib
from collections.abc import Iterator

import pytest


@contextlib.contextmanager
def raises_message(
    exc_type: type[BaseException],
    message: str,
    detail: object = None,
) -> Iterator[pytest.ExceptionInfo[BaseException]]:
    """Assert the block raises ``exc_type`` with exactly ``message``.

    ``detail`` is appended to the assertion the way a bare ``assert x, detail``
    would be, so a loop over a table of malformed programs can name the case
    that failed.  The :class:`pytest.ExceptionInfo` is yielded for the tests
    that go on to inspect the exception itself; note its ``value`` is only
    populated once the block has exited.
    """
    with pytest.raises(exc_type) as caught:
        yield caught
    assert str(caught.value) == message, detail
