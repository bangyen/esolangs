"""Shared public contracts, independent of language ownership."""

import sys
from unittest.mock import patch

import pytest

import esolangs
from esolangs.cli.hints import _did_you_mean
from esolangs.registry import CATALOG, SUGGESTION_CUTOFF, Catalog, canonical_id
from tests.support.reference import REFERENCE

_BY_ID = CATALOG._by_id


class TestPackageEntryPoint:
    """python -m esolangs dispatches to the CLI via esolangs/__main__.py."""

    def test_run_as_main(self, capsys: pytest.CaptureFixture[str]) -> None:
        import runpy

        with patch.object(sys, "argv", ["esolangs", "generate", REFERENCE, "0110"]):
            runpy.run_module("esolangs", run_name="__main__")
        out = capsys.readouterr().out
        assert esolangs.run(REFERENCE, out, stdin="01").unwrap().output == "1"


class TestASuggestionIsWorthLessThanSilence:
    """A 0.6 cutoff offers a language for the unrelated word ``snorey``."""

    @staticmethod
    def _typos(name: str) -> list[str]:
        """Dropped and transposed characters, keeping only real misses."""
        out = [name[:-1], name[0] + name[2:], name[1:]]
        if len(name) > 4:
            out.append(name[:2] + name[3:])
            out.append(name[:2] + name[3] + name[2] + name[4:])
        return [
            typo
            for typo in dict.fromkeys(out)
            if typo and canonical_id(typo) not in _BY_ID
        ]

    _JUNK = ("snorey", "zzzz", "xyz", "qqqqqq", "hello", "python", "asdf", "foo")

    def _score(self, cutoff: float) -> tuple[int, int, int]:
        """Return (typos rescued, typos tried, junk words given a guess)."""
        rescued = tried = 0
        for name in esolangs.list_languages():
            for typo in self._typos(name):
                tried += 1
                close = CATALOG._close_ids(typo, cutoff)
                rescued += name in [_BY_ID[c] for c in close]
        junk = sum(bool(CATALOG._close_ids(word, cutoff)) for word in self._JUNK)
        return rescued, tried, junk

    def test_the_cutoff_is_the_best_available_number(self) -> None:
        """The trade, recomputed: 0.6 costs junk and 0.7 costs rescues."""
        shipped = self._score(SUGGESTION_CUTOFF)
        assert shipped[2] == 0, "the shipped cutoff offers a guess for junk"
        # The positive control: at 0.6 the same rescues come back with junk.
        assert self._score(0.6)[0] == shipped[0]
        assert self._score(0.5)[2] > 0
        assert self._score(0.7)[0] < shipped[0]

    def test_a_name_head_is_suggested_never_resolved(self) -> None:
        """A distinctive prefix is suggested without becoming an alias."""
        longest = max(esolangs.list_languages(), key=len)
        catalog = Catalog([CATALOG.languages[longest]])
        key = canonical_id(longest).replace("_", "")
        for head in (key[:3], key[: len(key) // 3]):
            with pytest.raises(esolangs.UnknownLanguageError) as caught:
                catalog.resolve(head)
            assert longest in caught.value.suggestions, head

    def test_api_and_cli_withhold_guesses_for_junk(self) -> None:
        for word in self._JUNK:
            with pytest.raises(esolangs.UnknownLanguageError) as caught:
                esolangs.describe(word)
            assert caught.value.suggestions == (), word
            assert "did you mean" not in str(caught.value)
            assert "`esolangs list` shows all of them" in str(caught.value)

        assert _did_you_mean("snorey", esolangs.list_languages()) == ""
        assert "--width" in _did_you_mean("--wdith", ["--width", "--bits"])
