"""Unit tests for the EGL interpreter."""

import re

import pytest

from esolangs.interpreters.grid_based.egl import _advance, run
from esolangs.interpreters.io import ScriptedIO


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("", "must begin"),
        ("0,1:", "dimensions must be positive"),
        ("1,1:(", "unmatched parenthesis"),
        ("1,1:>", "moved outside"),
    ],
)
def test_malformed_program(code: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        run(code, ScriptedIO())


def test_a_close_without_an_open_is_rejected_at_the_transition() -> None:
    """``match_brackets`` rejects this at parse time, so only the pure
    transition can be asked what it does with a bare ``)``."""
    with pytest.raises(ValueError, match=re.escape("unmatched ')'")):
        _advance((0, 0, 0, (0,) * 4, ()), ")", {}, 2, 2)
