"""Shared listing and specification contracts."""

import re

import pytest

import esolangs
from esolangs.runtime._execution import interpreter_module
from tests.cli.test_cli import call_main
from tests.support.reference import REFERENCE

#: What a spec must not show: a private name, a raw Sphinx role, a repo path.
_MAINTAINER = re.compile(
    r"(?<![\w`.])`*_[a-z]\w*"
    r"|:(?:class|func|meth|mod|attr|exc|data|obj):`"
    r"|\b(?:src|tests)/[\w/.]+"
)


class TestMessagesNameTheThingThatIsWrong:
    """Shared public contract."""

    def test_the_details_legend_is_printed_with_the_details(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """It lived in `list --help` only, so the columns arrived unexplained."""
        out = call_main(["list", "--details"], capsys)
        assert out.splitlines()[0].strip().startswith("language")
        assert "gen=generator" in out.splitlines()[0]


class TestCapabilityListing:
    """Shared public contract."""

    def test_the_plain_listing_is_unchanged(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Scripts parse it, so the default output stays bare names."""
        names = call_main(["list"], capsys).split()
        assert REFERENCE in names


class TestEveryDumpSaysWhereTheAnswerIs:
    """Shared public contract."""

    def test_a_dump_has_a_pattern_or_a_note(self) -> None:
        """Either a regex that finds the answer, or prose that locates it."""
        silent = [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["answer_mode"] == "dump"
            and not esolangs.describe(name)["answer_pattern"]
            and not esolangs.describe(name)["answer_convention"]
        ]
        assert not silent, (
            f"dump languages that never say where the answer is: {silent}"
        )


class TestTheSpecIsReachable:
    """Shared public contract."""

    def test_every_language_has_one(self) -> None:
        """The claim the feature rests on: there is something to show."""
        for name in esolangs.list_languages():
            assert len(esolangs.describe(name)["spec"]) > 200, name

    def test_no_spec_shows_maintainer_detail(self) -> None:
        """Implementation notes are comments beside the code they explain."""
        leaks = {
            name: _MAINTAINER.findall(esolangs.describe(name)["spec"])
            for name in esolangs.list_languages()
        }
        leaks = {name: found for name, found in leaks.items() if found}
        assert not leaks, (
            f"a spec is its interpreter's and generator's module docstrings; "
            f"move these into comments beside the code they explain "
            f"(docs/CONTRIBUTING.md), or reword a language token that only "
            f"looks private (`_name`, a Sphinx role, a repo path): {leaks}"
        )

    def test_roles_render_and_the_leak_check_fires(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Positive control: a public role renders; a private name is caught."""
        module = interpreter_module(REFERENCE)
        monkeypatch.setattr(
            module,
            "__doc__",
            "Raises :class:`~esolangs.exceptions.HaltError`; :func:`_advance`.",
        )
        spec = esolangs.describe(REFERENCE)["spec"]
        assert spec == "Raises ``HaltError``; ``_advance``."
        assert _MAINTAINER.findall(spec) == ["``_advance"]


class TestSpecAbortsRatherThanReturningNothing:
    """Shared public contract."""

    def test_it_raises_when_there_is_no_docstring(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Simulated by emptying one, since the test run is not under -OO."""
        module = interpreter_module(REFERENCE)
        monkeypatch.setattr(module, "__doc__", None)
        with pytest.raises(esolangs.ProgramError, match="-OO"):
            esolangs.describe(REFERENCE)["spec"]

    def test_it_still_returns_the_text_normally(self) -> None:
        """The abort must not have eaten the ordinary path."""
        assert esolangs.describe(REFERENCE)["spec"].startswith("Interpreter for")
