"""Unsquare through the shared API, CLI and machinery."""

import esolangs
from esolangs._execution import interpreter_module


class TestTheSpecIsReachable:
    """The best documentation here was reachable only by guessing."""

    def test_it_is_the_interpreter_that_is_read(self) -> None:
        """Read, not stored, so it cannot drift from what it describes."""
        module = interpreter_module("Unsquare")
        assert esolangs.describe("Unsquare")["spec"] == (module.__doc__ or "").strip()
