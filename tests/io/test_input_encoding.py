"""Feeding a language its input bits is answerable without reading source."""

from __future__ import annotations

import pathlib

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.cli_hints import _template_hint
from esolangs.exceptions import ProgramError, TemplateError
from tests.api.test_language_coupling import REFERENCE
from tests.support.pick import languages
from tests.support.witness_tables import row_bits

XOR = "0110"
PARITY3 = "10010110"
SIMPLE = ("char_stream", "line_per_bit")


def _rows(language: str, table: str) -> str:
    """Run every row of ``table`` through a freshly generated program."""
    program = esolangs.generate(language, table)
    inputs = len(table).bit_length() - 1
    got = ""
    for row in range(len(table)):
        bits = row_bits(row, inputs)
        stdin = esolangs.encode_inputs(language, bits)
        got += esolangs.run(language, program, stdin=stdin, timeout=30)[-1:] or "?"
    return got


class TestTheExceptionalLanguages:
    """The languages whose input shape is not a line per bit."""

    @pytest.mark.parametrize(
        "language",
        [
            name
            for name in languages(boolean_generator=True, parameterized=False)
            if esolangs.describe(name)["input_shape"] not in SIMPLE
        ],
    )
    @pytest.mark.parametrize("table", [XOR, PARITY3])
    def test_the_encoding_computes_the_table(self, language: str, table: str) -> None:
        """Taglate at three inputs used to fail outright; the rest lied."""
        assert _rows(language, table) == table

    def test_every_reading_language_has_an_encoding(self) -> None:
        """``encode_inputs`` indexes the example table, which must cover all."""
        assert esolangs.encode_inputs(REFERENCE, [1, 0, 1]) == "101"
        for name in languages(boolean_generator=True):
            if esolangs.describe(name)["parameterized"]:
                with pytest.raises(esolangs.ArgumentError, match="reads no stdin"):
                    esolangs.encode_inputs(name, [0, 1])
            else:
                assert esolangs.encode_inputs(name, [0, 1])


class TestTemplatesAreNotWrapped:
    """A template's run of its character is one token to every wrapper."""

    @pytest.mark.parametrize("language", languages(parameterized=True))
    def test_a_width_leaves_a_template_intact(self, language: str) -> None:
        """A narrow width used to cut a slot in half, silently; a run is whole."""
        narrow = esolangs.generate(language, XOR, width=5)
        assert narrow.count(narrow.char) == sum(len(z) for z, _ in narrow.setters)
        assert _evaluate(language, narrow, inputs=2) == XOR


class TestRemainingGuards:
    """Small refusals added with these fixes."""

    @pytest.mark.parametrize("width", [0])
    def test_a_nonpositive_width_is_refused(self, width: int) -> None:
        """It returned the unwrapped program, looking like it had honoured it."""
        with pytest.raises(ValueError, match="width must be positive"):
            esolangs.generate(REFERENCE, XOR, width=width)

    def test_a_missing_path_is_a_programerror(self) -> None:
        with pytest.raises(ProgramError, match="cannot read"):
            esolangs.run(REFERENCE, pathlib.Path("nope/missing.txt"))

    def test_a_non_string_language_is_refused_by_name(self) -> None:
        """It leaked ``'NoneType' object has no attribute 'replace'``."""
        with pytest.raises(esolangs.UnknownLanguageError, match="got NoneType"):
            esolangs.generate(None, XOR)  # type: ignore[arg-type]

    def test_the_cli_hint_passes_through_an_unrelated_message(self) -> None:
        """Only the slot refusal names a Python call worth rewriting."""
        other = TemplateError("brainfuck reads its inputs rather than embedding them")
        assert _template_hint(other, "brainfuck") == str(other)


class TestEveryDeliberateErrorHasTheBase:
    """``except EsolangError`` is the whole handler, option errors included."""

    @pytest.mark.parametrize(
        "call",
        [
            lambda: esolangs.generate("brainfuck", XOR, width=0),
            lambda: esolangs.generate("brainfuck", XOR, width="20"),
            lambda: esolangs.run("brainfuck", "+.", timeout=0),
            lambda: esolangs.encode_inputs("brainfuck", [2, 0]),
        ],
    )
    def test_an_invalid_option_is_an_esolangerror(self, call: object) -> None:
        """These were bare ValueErrors, so the documented base class missed."""
        with pytest.raises(esolangs.ArgumentError) as exc:
            call()  # type: ignore[operator]
        assert isinstance(exc.value, esolangs.EsolangError)
        assert isinstance(exc.value, ValueError), "the old base still catches"

    def test_encode_inputs_refuses_a_non_bit(self) -> None:
        """A 2 encoded as a 1 and answered a different row, in silence."""
        with pytest.raises(esolangs.ArgumentError, match="must each be 0 or 1"):
            esolangs.encode_inputs("brainfuck", [2, 0])
