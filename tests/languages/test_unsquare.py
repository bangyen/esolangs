"""Unsquare through the shared API, CLI and machinery."""

import esolangs
from esolangs._execution import interpreter_module


class TestTheSpecIsReachable:
    """The best documentation here was reachable only by guessing."""

    def test_every_language_has_one(self) -> None:
        """The claim the feature rests on: there is something to show."""
        for name in esolangs.list_languages():
            assert len(esolangs.describe(name)["spec"]) > 200, name

    def test_it_is_the_interpreter_that_is_read(self) -> None:
        """Read, not stored, so it cannot drift from what it describes."""
        module = interpreter_module("Unsquare")
        assert esolangs.describe("Unsquare")["spec"] == (module.__doc__ or "").strip()
