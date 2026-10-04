"""Dig parser diagnostics."""

import pytest

from esolangs.interpreters.grid_based.dig import run
from esolangs.interpreters.io import IO
from tests.raises import raises_message


class TestDigEdgeCases:
    """Test edge cases and error conditions."""

    def test_the_empty_program_message_reads_exactly(self) -> None:
        """``match=`` only looks for a substring, so pin the whole message."""
        with raises_message(ValueError, "Dig program cannot be empty"):
            run([], io=IO())

    def test_blank_only_program_is_empty(self) -> None:
        """Programs of only blank lines are rejected, not crashing the mole."""
        with pytest.raises(ValueError, match="empty"):
            run(["\n"], io=IO())
        with pytest.raises(ValueError, match="empty"):
            run(["   ", "\t"], io=IO())
