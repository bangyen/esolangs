"""Sophie through the shared API, CLI and machinery."""

import difflib
import sys
from typing import Any
from unittest.mock import patch

import pytest

import esolangs
from esolangs import vm
from esolangs.cli_hints import _did_you_mean
from esolangs.registry import _BY_ID, SUGGESTION_CUTOFF, canonical_id


class TestPackageEntryPoint:
    """python -m esolangs dispatches to the CLI via esolangs/__main__.py."""

    def test_run_as_main(self, capsys: pytest.CaptureFixture[str]) -> None:
        import runpy

        with patch.object(sys, "argv", ["esolangs", "generate", "Sophie", "0110"]):
            runpy.run_module("esolangs", run_name="__main__")
        out = capsys.readouterr().out
        assert esolangs.run("Sophie", out, stdin="01") == "1"


@pytest.mark.medium
@pytest.mark.parametrize(
    ("detector", "hint"),
    [
        ("run_until_halt_or_all_branches_cycle", "branching_successors"),
        ("run_until_halt_or_ancestor", "frame_entry_key"),
        ("run_until_halt_or_growth", "rightward-growing tape"),
        ("run_until_halt_or_value_growth", "unbounded affine values"),
    ],
)
def test_unsupported_detectors_name_the_needed_capability(detector, hint):
    with pytest.raises(TypeError) as caught:
        getattr(vm, detector)(vm.make_vm("Sophie", ""))
    assert type(caught.value) is TypeError
    assert str(caught.value).startswith("Sophie is not ")
    assert hint in caught.value.__notes__[0]


def test_a_wrapping_language_really_reflows() -> None:
    """Sophie declares `wrap`; the positive control checks it really does."""
    wide = esolangs.generate("Sophie", "0110")
    narrow = esolangs.generate("Sophie", "0110", width=10)
    assert "\n" not in wide
    assert "\n" in narrow
    assert esolangs.describe("Sophie")["width_effect"] == "wrap"


class TestASuggestionIsWorthLessThanSilence:
    """0.6 offers ``Nope.`` for ``snorey``."""

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
                close = difflib.get_close_matches(
                    canonical_id(typo), _BY_ID, n=2, cutoff=cutoff
                )
                rescued += name in [_BY_ID[c] for c in close]
        junk = sum(
            bool(difflib.get_close_matches(canonical_id(w), _BY_ID, n=2, cutoff=cutoff))
            for w in self._JUNK
        )
        return rescued, tried, junk

    def test_the_cutoff_is_the_best_available_number(self) -> None:
        """The trade, recomputed: 0.6 costs junk and 0.7 costs rescues."""
        shipped = self._score(SUGGESTION_CUTOFF)
        assert shipped[2] == 0, "the shipped cutoff offers a guess for junk"
        # The positive control: at 0.6 the same rescues come back with junk.
        assert self._score(0.6)[0] == shipped[0]
        assert self._score(0.5)[2] > 0
        assert self._score(0.7)[0] < shipped[0]

    def test_a_word_that_is_not_close_gets_no_guess(self) -> None:
        with pytest.raises(esolangs.UnknownLanguageError) as caught:
            esolangs.describe("snorey")
        assert "did you mean" not in str(caught.value)
        assert "`esolangs list` shows all of them" in str(caught.value)

    def test_the_cli_shares_the_number(self) -> None:
        assert _did_you_mean("snorey", esolangs.list_languages()) == ""
        assert "--width" in _did_you_mean("--wdith", ["--width", "--bits"])


def _bounds(profile: dict[str, Any]) -> None:
    """The construction bounds the resource audit holds this generator to."""
    units = profile["source_units"]
    commands = profile["worst_row_commands"]
    memory = profile["peak_memory_cells"]
    stack = profile["peak_stack_items"]
    # No loop opcode: each executed command advances the source cursor.
    assert commands <= units
    assert memory == 1
    assert stack == 0
    assert profile["peak_control_stack_items"] == 0
    assert profile["peak_machine_bits"] <= 8 + units.bit_length() + 2


@pytest.mark.medium
def test_resource_bounds() -> None:
    """The resource audit counts a UTF-8 byte per source unit."""
    from tests.support.screen_support import audit
    from tests.support.screen_support import resource_corpus as corpus

    result = audit("Sophie", 3, corpus(3)["parity"], _bounds)
    assert result["source_utf8_bits"] == 8 * result["source_units"]
