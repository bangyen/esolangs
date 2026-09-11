"""What a caller needs to feed a program and judge what comes back.

A third blind pass, and the same class of bug as the two before it: the
facts that decide a right answer from a wrong one existed as data and were
*described* wrongly somewhere else.  This round the wrong description was in
the prose, not in a test suite -- the README, ``run --help`` and
``encode --help`` all said Clockwise and Fargo want their bits on one line,
and Fargo wants the row index as a decimal number.  Following the sentence
returned 0 where the answer was 1, exit 0, no warning, and it hides below
four inputs because the decimal and binary readings coincide there.

So the first class below recomputes the exceptional set from
:func:`esolangs.describe` and checks the prose against it.  A fourth
language with a fourth shape, or a shape that changes, now fails here
instead of being read and believed.
"""

from __future__ import annotations

import pathlib
import re

import pytest

import esolangs
from esolangs.cli import HELP

README = (pathlib.Path(__file__).parents[1] / "README.md").read_text()

#: How each exceptional shape has to be *described*, as a regex over the
#: prose.  Keyed by the ``input_shape`` the data reports, so a language that
#: changes shape changes which sentence it has to appear in.
_SHAPE_PROSE = {
    "one_line": r"(all |every |them all )?(bits? )?.{0,12}on one line",
    "row_index": r"row index as (one|a single) decimal number|row index as one decimal",
    "line_per_bit_padded": r"pads an odd input count with a leading zero",
}


class TestTheProseMatchesTheData:
    """Three documents named the shapes; one of the four names was wrong."""

    def test_exactly_three_languages_have_an_exceptional_shape(self) -> None:
        """Plus Grapheme's alphabet, which is the fourth exception."""
        odd = {
            name: esolangs.describe(name)["input_shape"]
            for name in esolangs.list_languages()
            if esolangs.describe(name)["input_shape"] != "line_per_bit"
        }
        assert odd == {
            "Clockwise": "one_line",
            "Fargo": "row_index",
            "Taglate": "line_per_bit_padded",
        }

    @pytest.mark.parametrize("document", ["README", "run", "encode"])
    def test_each_document_describes_each_shape_correctly(self, document: str) -> None:
        """Fargo was lumped in with Clockwise in all three at once."""
        # Whitespace collapsed first: these documents are hard-wrapped, so a
        # newline lands in the middle of the phrase being matched.
        text = re.sub(r"\s+", " ", README if document == "README" else HELP[document])
        for name in esolangs.list_languages():
            shape = esolangs.describe(name)["input_shape"]
            if shape == "line_per_bit":
                continue
            assert name in text, (document, name)
            naming = [s for s in re.split(r"(?<=[.,;])\s+", text) if name in s]
            # Some sentence has to describe it correctly...
            assert any(re.search(_SHAPE_PROSE[str(shape)], s) for s in naming), (
                document,
                name,
                naming,
            )
            # ...and none may describe it as a shape it does not have.  This
            # second half is the one that catches the bug that prompted the
            # test: "Clockwise and Fargo want them all on one line" names
            # Fargo in a sentence matching `one_line`, which is Clockwise's
            # shape.  Checking only the first half would have passed it,
            # since the same documents also mention Fargo's real shape.
            for other, pattern in _SHAPE_PROSE.items():
                if other == shape:
                    continue
                wrong = [s for s in naming if re.search(pattern, s)]
                assert not wrong, (document, name, shape, other, wrong)

    def test_the_row_index_really_is_a_row_index(self) -> None:
        """The claim the prose got wrong, stated as an executable fact."""
        assert esolangs.encode_inputs("Fargo", [1, 1, 1, 1]) == "15\n"
        assert esolangs.encode_inputs("Clockwise", [1, 1, 1, 1]) == "1111"

    def test_following_the_old_sentence_would_now_be_caught(self) -> None:
        """A bit-per-line Fargo input is the wrong row, and only n>=4 shows it."""
        table = "0000000000000001"  # AND of four inputs
        program = esolangs.generate("Fargo", table)
        right = esolangs.run(
            "Fargo", program, esolangs.encode_inputs("Fargo", [1, 1, 1, 1]), timeout=20
        )
        wrong = esolangs.run("Fargo", program, "1111\n", timeout=20)
        assert esolangs.read_answer("Fargo", right) == "1"
        assert esolangs.read_answer("Fargo", wrong) == "0"


class TestEncodeInputsCanCheckItsArity:
    """The one function whose purpose is to stop a silent mis-encoding."""

    def test_a_wrong_bit_count_is_refused_when_the_table_is_given(self) -> None:
        """Three bits at a four-row table encoded as cheerfully as two."""
        with pytest.raises(esolangs.ArgumentError, match="2 inputs, but 3 bits"):
            esolangs.encode_inputs("Fargo", [1, 0, 1], "0110")

    def test_the_right_count_passes(self) -> None:
        """And still encodes the shape it always did."""
        assert esolangs.encode_inputs("Fargo", [1, 0], "0110") == "2\n"

    def test_the_table_stays_optional(self) -> None:
        """Every existing caller passes two arguments and must keep working."""
        assert esolangs.encode_inputs("Fargo", [1, 0]) == "2\n"

    def test_a_malformed_table_is_named_as_one(self) -> None:
        """Not reported as a bit-count mismatch against a nonsense arity."""
        with pytest.raises(esolangs.TruthTableError):
            esolangs.encode_inputs("brainfuck", [1, 0], "011")


class TestATemplateKnowsWhoseItIs:
    """Filling one as the wrong language ran, and answered a different row."""

    def test_a_foreign_template_is_refused(self) -> None:
        """It substituted RAM0's setter into a Minifuck program and answered 0."""
        template = esolangs.generate("Minifuck", "0110")
        with pytest.raises(esolangs.TemplateError, match="came from generate"):
            esolangs.instantiate("RAM0", template, [0, 1])

    def test_its_own_language_still_fills_it(self) -> None:
        """And the filled program answers the row it was asked for."""
        template = esolangs.generate("Minifuck", "0110")
        program = esolangs.instantiate("Minifuck", template, [0, 1])
        assert (
            esolangs.read_answer(
                "Minifuck", esolangs.run("Minifuck", program, timeout=20)
            )
            == "1"
        )

    def test_the_name_is_resolved_before_it_is_compared(self) -> None:
        """A case variant is the same language, not a mismatch."""
        template = esolangs.generate("minifuck", "0110")
        assert esolangs.instantiate("MINIFUCK", template, [0, 1])

    def test_a_plain_string_is_accepted_unchecked(self) -> None:
        """The tag cannot survive a file, so its absence must not be an error."""
        template = str(esolangs.generate("Minifuck", "0110"))
        assert esolangs.instantiate("Minifuck", template, [0, 1])

    def test_a_template_is_still_a_string_everywhere_else(self) -> None:
        """Callers print it, slice it and write it; none should notice the tag."""
        template = esolangs.generate("Minifuck", "0110")
        assert isinstance(template, str)
        assert template == str(template)
        assert "{X0}" in template


class TestExamplePathsWorkFromAnywhere:
    """The recipe this package advertises worked from one directory."""

    def test_they_are_absolute(self) -> None:
        """``run(lang, Path(describe(lang)["examples"][0]))`` is documented."""
        for name in esolangs.list_languages():
            for example in esolangs.describe(name)["examples"]:  # type: ignore[union-attr]
                assert pathlib.Path(str(example)).is_absolute(), (name, example)

    def test_the_advertised_recipe_runs_from_another_directory(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A chdir away it was ``cannot read examples/boolean/brainfuck.txt``."""
        example = pathlib.Path(str(esolangs.describe("brainfuck")["examples"][0]))
        monkeypatch.chdir(tmp_path)
        assert esolangs.run("brainfuck", example, "1\n0\n", timeout=20)


class TestTheVerifierIsShipped:
    """Two blind readers and the test suite each wrote this same function."""

    def test_evaluate_returns_the_table_the_program_computes(self) -> None:
        """So a mismatch is locatable rather than summarized to False."""
        assert esolangs.evaluate("brainfuck", "0110") == "0110"

    def test_verify_is_the_comparison(self) -> None:
        """The verdict, for callers who only want the verdict."""
        assert esolangs.verify("brainfuck", "0110") is True

    @pytest.mark.parametrize(
        "name", ["Fargo", "Clockwise", "Grapheme", "Taglate", "Minifuck", "RAM0"]
    )
    def test_it_covers_the_languages_that_need_per_language_knowledge(
        self, name: str
    ) -> None:
        """The four odd input shapes and two template languages."""
        assert esolangs.verify(name, "0110")

    def test_it_reads_the_termination_polarity_as_data(self) -> None:
        """Rather than assuming halting is the zero."""
        facts = esolangs.describe("123")
        assert facts["answer_encoding"] == ("halts", "diverges")
        assert esolangs.verify("123", "0110", timeout=5)

    def test_a_malformed_table_is_refused_before_anything_runs(self) -> None:
        """Named as a table, not as whichever generator saw it first."""
        with pytest.raises(esolangs.TruthTableError):
            esolangs.evaluate("brainfuck", "011")

    @pytest.mark.slow
    def test_every_language_verifies(self) -> None:
        """69/69, through the public function rather than a local copy."""
        failed = [
            n for n in esolangs.list_languages() if not esolangs.verify(n, "0110")
        ]
        assert not failed


class TestTheNewChecksRefuseTheirOwnBadInput:
    """The arguments the round's new parameters can be given wrongly."""

    def test_encode_inputs_names_a_non_string_table(self) -> None:
        """It is a table's *type* that is wrong, not the bit count."""
        with pytest.raises(esolangs.TruthTableError, match="got int"):
            esolangs.encode_inputs("brainfuck", [1, 0], 110)  # type: ignore[arg-type]

    def test_evaluate_names_a_non_string_table(self) -> None:
        """Reported before any generator sees it, for the same reason."""
        with pytest.raises(esolangs.TruthTableError, match="got list"):
            esolangs.evaluate("brainfuck", [0, 1, 1, 0])  # type: ignore[arg-type]

    def test_machine_traits_refuses_an_unregistered_name(self) -> None:
        """Same contract as ``make_vm``, which is the only other reader."""
        from esolangs.vm import machine_traits

        with pytest.raises(esolangs.UnknownLanguageError):
            machine_traits("Nonexistent")


class TestADeliberateRefusalIsAnEsolangError:
    """The package promises it, and the five refusals broke the promise.

    Every generator cap raised a plain ``ValueError`` -- Interprogck8 a
    *private* ``_StuckError`` nothing exported -- so ``except EsolangError``
    around a registry sweep, the idiom the docs advertise, crashed on the
    first of them.
    """

    #: The five that stop rather than build.  Only these are built here: the
    #: other sixty-four succeed at n=11 and several take minutes to do it.
    _REFUSERS = ("Factor", "Interprogck8", "Polynomial", "WII2D", "ZTOALC L")

    @staticmethod
    def _big_table() -> str:
        """Return a dense n=11 table, past every cap below."""
        import random

        rng = random.Random(7)
        return "".join(rng.choice("01") for _ in range(2048))

    @pytest.mark.slow
    @pytest.mark.parametrize("name", _REFUSERS)
    def test_the_refusal_is_catchable(self, name: str) -> None:
        """And by the documented base class, not only the specific one."""
        with pytest.raises(esolangs.GeneratorCapError):
            esolangs.generate(name, self._big_table())

    @pytest.mark.slow
    @pytest.mark.parametrize("name", _REFUSERS)
    def test_the_documented_idiom_catches_it(self, name: str) -> None:
        """``except EsolangError`` is what the package docstring promises."""
        with pytest.raises(esolangs.EsolangError):
            esolangs.generate(name, self._big_table())

    def test_it_is_still_a_value_error(self) -> None:
        """Callers catching ValueError must not be broken by the new class."""
        assert issubclass(esolangs.GeneratorCapError, ValueError)
        assert issubclass(esolangs.GeneratorCapError, esolangs.EsolangError)

    def test_it_is_exported(self) -> None:
        """A refusal nobody can name is a refusal nobody can catch."""
        assert "GeneratorCapError" in esolangs.__all__

    @pytest.mark.slow
    def test_no_private_name_leaks_into_a_message(self) -> None:
        """WII2D's named its own module-private constant at the reader."""
        with pytest.raises(esolangs.GeneratorCapError) as exc:
            esolangs.generate("WII2D", self._big_table())
        assert "_WII2D" not in str(exc.value)


class TestWidthEffectSaysWhatWidthDoes:
    """One flag, three behaviours, and no way to tell them apart.

    ``width_aware`` answered a narrower question -- whether the generator
    takes the width itself -- so it was ``False`` both for Sophie, whose
    program *is* reflowed, and for Clockwise, which ignores the width
    entirely.  A reader reported being unable to work out what the field
    meant without reading the source, which is the tripwire.
    """

    def test_every_language_declares_one_of_three(self) -> None:
        """A fourth value would be a behaviour nobody documented."""
        seen = {esolangs.describe(n)["width_effect"] for n in esolangs.list_languages()}
        assert seen <= {"wrap", "layout", "none"}

    def test_layout_is_exactly_the_width_aware_generators(self) -> None:
        """The old field is the new field's `layout` case, and only that."""
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            assert (facts["width_effect"] == "layout") == facts["width_aware"], name

    @pytest.mark.slow
    def test_the_declaration_matches_what_width_actually_does(self) -> None:
        """The drift guard: `none` must really be a no-op."""
        wrong = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            plain = esolangs.generate(name, "0110")
            narrow = esolangs.generate(name, "0110", 20)
            if facts["width_effect"] == "none" and plain != narrow:
                wrong.append(f"{name}: declared none but --width changed it")
            # `wrap` and `layout` may coincide on a program already narrower
            # than the width, so only the `none` direction is decidable here.
        assert not wrong, "\n".join(wrong)

    def test_a_wrapping_language_really_reflows(self) -> None:
        """The positive control for the check above, which only tests `none`."""
        wide = esolangs.generate("Sophie", "0110")
        narrow = esolangs.generate("Sophie", "0110", 10)
        assert "\n" not in wide
        assert "\n" in narrow
        assert esolangs.describe("Sophie")["width_effect"] == "wrap"
