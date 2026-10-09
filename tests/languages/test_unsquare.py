"""Unsquare through the shared API, CLI and machinery."""

import json

import pytest

import esolangs
from esolangs._execution import interpreter_module
from tests.cli_support import call_both


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

    def test_it_resolves_a_name_like_everything_else(self) -> None:
        """A spelling that works everywhere else has to work here."""
        assert (
            esolangs.describe("BRAINFUCK")["spec"]
            == esolangs.describe("brainfuck")["spec"]
        )
        assert (
            esolangs.describe(" Unsquare ")["spec"]
            == esolangs.describe("Unsquare")["spec"]
        )
        with pytest.raises(esolangs.UnknownLanguageError):
            esolangs.describe("nosuchlang")["spec"]

    def test_the_cli_prints_it(self, capsys: pytest.CaptureFixture[str]) -> None:
        """And prints the text, not a record with the text in it."""
        out, _err = call_both(["describe", "--spec", "Unsquare"], capsys)
        assert out.strip() == esolangs.describe("Unsquare")["spec"]

    def test_json_and_spec_together_give_a_field(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A caller scripting it wants the record *and* the prose."""
        out, _err = call_both(["describe", "--json", "--spec", "brainfuck"], capsys)
        payload = json.loads(out)
        assert payload["spec"] == esolangs.describe("brainfuck")["spec"]
        assert payload["name"] == "brainfuck"

    def test_the_pointer_names_the_resolved_name(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Copying the line has to work, which means the canonical spelling."""
        out, _err = call_both(["describe", "BRAINFUCK"], capsys)
        assert "--spec brainfuck" in out
