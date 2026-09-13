"""Feeding a language its input bits is answerable without reading source.

Four languages do not take one ``0``/``1`` line per bit, and every one of
them was found the same way: a reader fed digits a line at a time and got a
plausible wrong answer -- or, for Taglate at three inputs, an
input-exhausted error.  The facts existed in a table in the test suite,
where no caller could reach them.  :func:`esolangs.encode_inputs` is that
table, shipped; these tests hold it to the interpreters.
"""

from __future__ import annotations

import pathlib

import pytest

import esolangs
from esolangs.cli import _template_hint
from esolangs.exceptions import ProgramError, TemplateError
from esolangs.registry import LANGUAGES, example_stems

XOR = "0110"
PARITY3 = "10010110"


def _rows(language: str, table: str) -> str:
    """Run every row of ``table`` through a freshly generated program."""
    program = esolangs.generate(language, table)
    inputs = len(table).bit_length() - 1
    got = ""
    for row in range(len(table)):
        bits = [(row >> (inputs - 1 - i)) & 1 for i in range(inputs)]
        stdin = esolangs.encode_inputs(language, bits)
        got += esolangs.run(language, program, stdin=stdin, timeout=30)[-1:] or "?"
    return got


class TestTheExceptionalLanguages:
    """The four whose input shape is not a line per bit."""

    @pytest.mark.parametrize(
        ("language", "bits", "expected"),
        [
            ("brainfuck", [1, 0, 1], "1\n0\n1\n"),
            ("Grapheme", [1, 0, 1], "A\n%\nA\n"),  # a "0" line reads as true
            ("Clockwise", [1, 0, 1], "101"),  # seven bits per character
            ("Fargo", [1, 0, 1], "5\n"),  # one number, indexed by bit
            ("Taglate", [1, 0, 1], "0\n1\n0\n1\n"),  # the leading ghost digit
            ("Taglate", [1, 0], "1\n0\n"),  # an even arity takes no ghost
        ],
    )
    def test_the_encoding_is_what_the_language_reads(
        self, language: str, bits: list[int], expected: str
    ) -> None:
        assert esolangs.encode_inputs(language, bits) == expected

    @pytest.mark.parametrize("language", ["Grapheme", "Clockwise", "Fargo", "Taglate"])
    @pytest.mark.parametrize("table", [XOR, PARITY3])
    def test_the_encoding_computes_the_table(self, language: str, table: str) -> None:
        """Taglate at three inputs used to fail outright; the rest lied."""
        assert _rows(language, table) == table

    def test_describe_reports_the_shape(self) -> None:
        assert esolangs.describe("Clockwise")["input_shape"] == "one_line"
        assert esolangs.describe("Fargo")["input_shape"] == "row_index"
        assert esolangs.describe("brainfuck")["input_shape"] == "line_per_bit"

    def test_every_reading_language_has_an_encoding(self) -> None:
        """``encode_inputs`` indexes the example table, which must cover all.

        The parameterized languages read no stdin at all, and asking for
        theirs is refused rather than answered -- ``instantiate`` is where
        their bits go.
        """
        assert set(example_stems()) == {lang.id for lang in LANGUAGES.values()}
        for name in esolangs.list_languages():
            if esolangs.describe(name)["parameterized"]:
                with pytest.raises(esolangs.ArgumentError, match="reads no stdin"):
                    esolangs.encode_inputs(name, [0, 1])
            else:
                assert esolangs.encode_inputs(name, [0, 1])


class TestTemplatesAreNotWrapped:
    """A ``{Xi}`` slot is not a token any wrapper knows."""

    @pytest.mark.parametrize("language", ["Home Row", "123", "A Painter Ant", "Eval"])
    def test_a_width_leaves_a_template_intact(self, language: str) -> None:
        """A narrow width used to cut ``{X1}`` in half, silently."""
        template = esolangs.generate(language, XOR, width=5)
        assert "{X0}" in template
        assert "{X1}" in template

    def test_the_width_applies_once_the_bits_are_in(self) -> None:
        template = esolangs.generate("Home Row", XOR)
        filled = esolangs.instantiate("Home Row", template, [0, 1], width=10)
        assert max(len(line) for line in filled.splitlines()) <= 10

    def test_a_wrapped_instantiation_still_computes_the_table(self) -> None:
        template = esolangs.generate("Home Row", XOR)
        got = "".join(
            esolangs.run(
                "Home Row",
                esolangs.instantiate("Home Row", template, [a, b], width=10),
                timeout=30,
            )
            for a in (0, 1)
            for b in (0, 1)
        )
        assert got == XOR


class TestRemainingGuards:
    """Small refusals added with these fixes."""

    @pytest.mark.parametrize("width", [0, -5])
    def test_a_nonpositive_width_is_refused(self, width: int) -> None:
        """It returned the unwrapped program, looking like it had honoured it."""
        with pytest.raises(ValueError, match="width must be positive"):
            esolangs.generate("brainfuck", XOR, width=width)

    def test_a_missing_path_is_a_programerror(self) -> None:
        with pytest.raises(ProgramError, match="cannot read"):
            esolangs.run("brainfuck", pathlib.Path("nope/missing.txt"))

    def test_a_non_string_language_is_refused_by_name(self) -> None:
        """It leaked ``'NoneType' object has no attribute 'replace'``."""
        with pytest.raises(esolangs.UnknownLanguageError, match="got NoneType"):
            esolangs.generate(None, XOR)  # type: ignore[arg-type]

    def test_the_cli_hint_passes_through_an_unrelated_message(self) -> None:
        """Only the slot refusal names a Python call worth rewriting."""
        other = TemplateError("brainfuck reads its inputs rather than embedding them")
        assert _template_hint(other, "brainfuck") == str(other)


class TestAnswerMode:
    """The structured counterpart to the ``answer_convention`` prose."""

    def test_every_language_declares_one_of_three_modes(self) -> None:
        modes = {esolangs.describe(n)["answer_mode"] for n in esolangs.list_languages()}
        assert modes == {"output", "termination", "dump"}

    def test_taglates_shape_names_its_padding(self) -> None:
        """Plain ``line_per_bit`` hid the pad digit its n=3 program needs."""
        assert esolangs.describe("Taglate")["input_shape"] == "line_per_bit_padded"

    @pytest.mark.slow
    def test_output_mode_means_the_printed_answer_is_the_table(self) -> None:
        """The classification is held to the interpreters, not just asserted.

        A structured field that lies is worse than the prose it replaces, so
        every language claiming ``output`` is run: the last non-whitespace
        character of each row must be that row of the table.
        """
        wrong = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if facts["parameterized"] or facts["answer_mode"] != "output":
                continue
            program = esolangs.generate(name, XOR)
            got = "".join(
                esolangs.run(
                    name,
                    program,
                    stdin=esolangs.encode_inputs(name, [(row >> 1) & 1, row & 1]),
                    timeout=30,
                ).strip()[-1:]
                or "?"
                for row in range(4)
            )
            if got != XOR:
                wrong.append((name, got))
        assert wrong == []


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
