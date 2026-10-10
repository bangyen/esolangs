"""Termination helpers preserve undecided results."""

from unittest.mock import patch

import pytest

from esolangs.exceptions import ExecutionTimeoutError
from tests import divergence


def test_undecided_fallback_timeout_propagates() -> None:
    with (
        patch.object(divergence, "diverges", return_value=None),
        patch.object(
            divergence.esolangs, "run", side_effect=ExecutionTimeoutError("undecided")
        ),
        pytest.raises(ExecutionTimeoutError, match="undecided"),
    ):
        divergence.terminates("fixture", "source", "", 0.001)


@pytest.mark.parametrize("diverges", [False, True])
def test_proven_verdict_never_uses_a_clock(diverges) -> None:
    with (
        patch.object(divergence, "diverges", return_value=diverges),
        patch.object(
            divergence.esolangs, "run", side_effect=AssertionError("not needed")
        ),
    ):
        assert divergence.terminates("fixture", "source", "", 0.001) is not diverges


def test_halting_fallback_returns_true() -> None:
    with (
        patch.object(divergence, "diverges", return_value=None),
        patch.object(divergence.esolangs, "run", return_value=""),
    ):
        assert divergence.terminates("fixture", "source", "", 0.001)
