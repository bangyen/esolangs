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

import contextlib
import difflib
import pathlib
import re

import pytest

import esolangs
from esolangs import cli
from esolangs.cli import HELP
from esolangs.registry import _BY_ID, SUGGESTION_CUTOFF, canonical_id

README = (pathlib.Path(__file__).parents[1] / "README.md").read_text()

#: How each exceptional shape has to be *described*, as a regex over the
#: prose.  Keyed by the ``input_shape`` the data reports, so a language that
#: changes shape changes which sentence it has to appear in.
_SHAPE_PROSE = {
    "one_line": r"(all |every |them all )?(bits? )?.{0,12}on one line",
    "row_index": r"row index as (one|a single) decimal number|row index as one decimal",
    "line_per_bit_padded": r"pads an odd input count with a leading zero",
}


@pytest.mark.filterwarnings("ignore::UserWarning")
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


class TestEveryAuditedCapIsCatchable:
    """The n=11 probe that found the first five was bounded by n=11.

    NoComment first refuses at n=12, so it escaped that sweep and still
    raised a bare ``ValueError`` -- and a reader following the try/except
    the previous round *added to the docstring* was met with an uncaught
    exception.  The fix for a class of bug cannot be found by widening the
    sweep that missed it, so the remaining sites were audited by reading.
    """

    def test_nocomment_is_catchable_at_the_size_it_refuses(self) -> None:
        """The confirmed escape, at the first arity that triggers it."""
        with pytest.raises(esolangs.GeneratorCapError, match="cell"):
            esolangs.generate("NoComment", "01" * (1 << 11))

    def test_it_is_catchable_through_evaluate_too(self) -> None:
        """It leaked through ``evaluate`` identically."""
        with pytest.raises(esolangs.GeneratorCapError):
            esolangs.evaluate("NoComment", "01" * (1 << 11))

    @pytest.mark.slow
    def test_nothing_escapes_the_contract_at_twelve_inputs(self) -> None:
        """A periodic table, so the generators that blow up stay small."""
        table = "0010" * (1 << 10)
        escaped = []
        for name in esolangs.list_languages():
            try:
                esolangs.generate(name, table)
            except esolangs.EsolangError:
                pass
            except Exception as exc:
                escaped.append(f"{name}: {type(exc).__name__}")
        assert not escaped, escaped

    def test_the_docstring_states_no_count(self) -> None:
        """It said "Five do" and six do; a tally in prose is a second copy."""
        assert esolangs.generate.__doc__ is not None
        assert "Five do" not in esolangs.generate.__doc__


@pytest.mark.filterwarnings("ignore::UserWarning")
class TestGraphemeReadsWhatTheDocsNowSay:
    """The stated mechanism was wrong, and so was its stated direction."""

    def test_only_an_a_line_reads_as_one(self) -> None:
        """'0', '1', 'x' and ' ' are all non-empty and all read as 0."""
        program = esolangs.generate("Grapheme", "01")
        answers = {}
        for line in ("A", "%", "0", "1", "x", " "):
            output = esolangs.run("Grapheme", program, line + "\n", timeout=10)
            answers[line] = esolangs.read_answer("Grapheme", output)
        assert answers == {
            "A": "1",
            "%": "0",
            "0": "0",
            "1": "0",
            "x": "0",
            " ": "0",
        }

    def test_the_convention_no_longer_claims_truthiness(self) -> None:
        """It said a 0/1 line reads as a 1; it reads as a 0."""
        note = str(esolangs.describe("Grapheme")["answer_convention"])
        assert "non-empty string" not in note
        assert "ord(line[0]) - 65" in note

    def test_naive_input_answers_the_all_zeros_row(self) -> None:
        """The true consequence: every bit reads 0, so you get row 0."""
        table = "0001"  # AND: row 0 is 0, row 3 is 1
        program = esolangs.generate("Grapheme", table)
        output = esolangs.run("Grapheme", program, "1\n1\n", timeout=10)
        assert esolangs.read_answer("Grapheme", output) == table[0]


class TestBreakAtChecksTheKindOfPosition:
    """Both wrong-kind breakpoints were stored and could never fire."""

    def test_a_tuple_is_refused_where_the_ip_is_an_index(self) -> None:
        """brainfuck's ip is an int."""
        program = esolangs.generate("brainfuck", "0110")
        debugger = esolangs.make_debugger("brainfuck", program, "0\n1\n")
        with pytest.raises(esolangs.ArgumentError, match="could never fire"):
            debugger.break_at((1, 2))

    def test_an_index_is_refused_where_the_ip_is_a_coordinate(self) -> None:
        """Alight's is a 4-tuple."""
        program = esolangs.generate("Alight", "0110")
        debugger = esolangs.make_debugger("Alight", program, "0\n1\n")
        with pytest.raises(esolangs.ArgumentError, match="could never fire"):
            debugger.break_at(10)

    def test_the_right_kind_is_accepted(self) -> None:
        """And still fires, which is the point of checking the other."""
        program = esolangs.generate("brainfuck", "0110")
        debugger = esolangs.make_debugger("brainfuck", program, "0\n1\n")
        debugger.break_at(0)
        assert debugger.run(max_steps=100) == "breakpoint"

    def test_the_arity_is_not_checked(self) -> None:
        """It varies within a run, so checking it would refuse valid ones."""
        program = esolangs.generate("Alight", "0110")
        debugger = esolangs.make_debugger("Alight", program, "0\n1\n")
        debugger.break_at((1, 2))  # wrong arity for Alight, accepted


@pytest.mark.filterwarnings("ignore::UserWarning")
class TestWhatHappensWhenAProgramIsUnderfed:
    """``run`` promised an exception for all sixty-nine.  Forty-five give it.

    A three-input program fed two bits: most raise, and seven take the
    exhausted read as a *value*, so the program answers a different row of
    its table with nothing in the output to show for it.  That convention
    was audited against the wiki pages and settled deliberately, so it is
    declared rather than rewritten -- but the promise was false and a
    caller had no way to find out for which languages.
    """

    TABLE = "10010110"  # n = 3

    def _underfed(self, name: str) -> tuple[str, str | None]:
        """Return ``(outcome, answer)`` for ``name`` fed one bit too few."""
        program = esolangs.generate(name, self.TABLE)
        short = esolangs.encode_inputs(name, [1, 0])
        try:
            output = esolangs.run(name, program, short, timeout=10)
        except esolangs.InputExhaustedError:
            return "raised", None
        except esolangs.EsolangError:
            return "language error", None
        try:
            return "answered", esolangs.read_answer(name, output)
        except esolangs.EsolangError:
            return "unreadable", None

    @pytest.mark.slow
    def test_only_the_declared_languages_answer_an_underfed_program(self) -> None:
        """The census, as a sweep: the flag and the behaviour must agree."""
        mismatched = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if facts["parameterized"]:
                continue  # no stdin to underfeed
            if facts["input_shape"] == "one_line":
                # Underfeeding a one-line language gives it a *shorter
                # string*, not a read past an end, so there is no EOF to
                # declare and nothing that could detect it.  Exempted by
                # its shape rather than by its name.
                continue
            outcome, _answer = self._underfed(name)
            declared = bool(facts["eof_is_a_value"])
            if outcome == "answered" and not declared:
                mismatched.append(f"{name}: answered but does not declare it")
            if outcome == "raised" and declared:
                mismatched.append(f"{name}: declares eof_is_a_value but raised")
        assert not mismatched, "\n".join(mismatched)

    @pytest.mark.slow
    def test_most_languages_raise(self) -> None:
        """The norm, counted, so a regression that erodes it is visible."""
        raised = sum(
            1
            for name in esolangs.list_languages()
            if not esolangs.describe(name)["parameterized"]
            and self._underfed(name)[0] == "raised"
        )
        # 43 of the 52 that read stdin, measured.  Pinned exactly, so that
        # a change which quietly moves a language out of the norm shows up
        # here rather than in a docstring nobody re-derives.
        assert raised == 43

    def test_the_trait_is_reported_by_describe(self) -> None:
        """A caller must be able to learn this without underfeeding one."""
        assert esolangs.describe("DINAC")["eof_is_a_value"] is True
        assert esolangs.describe("brainfuck")["eof_is_a_value"] is False

    def test_clockwise_is_not_marked_because_it_never_reads_past_an_end(
        self,
    ) -> None:
        """Its underfed input is a shorter one-line string: no EOF happens."""
        assert esolangs.describe("Clockwise")["eof_is_a_value"] is False
        outcome, _answer = self._underfed("Clockwise")
        assert outcome == "answered"

    def test_run_no_longer_promises_the_exception_everywhere(self) -> None:
        """The sentence that was false for seven languages."""
        assert esolangs.run.__doc__ is not None
        assert "eof_is_a_value" in esolangs.run.__doc__


class TestTheTerminationVocabularyIsExported:
    """A reader hand-copied this tuple and said so."""

    def test_it_matches_what_describe_reports(self) -> None:
        """The same two strings, in the order the polarity is read from."""
        for name in ("123", "ArrowQueue", "Point Break"):
            assert (
                esolangs.describe(name)["answer_encoding"]
                == esolangs.TERMINATION_OUTCOMES
            )

    def test_it_is_exported(self) -> None:
        """Beside ``STOP_REASONS``, which closed the same gap for stopping."""
        assert "TERMINATION_OUTCOMES" in esolangs.__all__


class TestCapMessagesNameOnlyReachableRemedies:
    """Factor's told you to pass a parameter the public API has not got."""

    @pytest.mark.slow
    def test_factor_does_not_name_a_private_knob(self) -> None:
        """`generate(language, truth_table, width)` has no `max_digits`."""
        import random

        rng = random.Random(7)
        table = "".join(rng.choice("01") for _ in range(2048))
        with pytest.raises(esolangs.GeneratorCapError) as exc:
            esolangs.generate("Factor", table)
        assert "max_digits" not in str(exc.value)


class TestBreakAtNamesTheKindNotTheValue:
    """It said "ip is 0" where it meant "ip is an index"."""

    def test_the_message_describes_the_kind(self) -> None:
        """A reader cannot generalize from one position's value."""
        program = esolangs.generate("brainfuck", "0110")
        debugger = esolangs.make_debugger("brainfuck", program, "0\n1\n")
        with pytest.raises(esolangs.ArgumentError, match="is an index"):
            debugger.break_at((1, 2))


class TestTheStdinJudgeIsReachableFromPython:
    """The one place the API was weaker than the command line."""

    def test_it_accepts_what_encode_inputs_builds(self) -> None:
        """The check must never fire on this package's own encoding.

        The sweep that matters: a judge which rejects the correct stdin for
        any language is worse than no judge, because the correct stdin is
        what every documented path produces.
        """
        wrong = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if not facts["reads_input"]:
                continue
            for table, bits in (("0110", [1, 0]), ("00010111", [1, 0, 1])):
                stdin = esolangs.encode_inputs(name, bits, table)
                try:
                    esolangs.check_stdin(name, stdin, table)
                except esolangs.EsolangError as exc:
                    wrong.append(f"{name} n={len(bits)}: {exc}")
        assert not wrong, "\n".join(wrong)

    def test_it_catches_the_wrong_alphabet(self) -> None:
        """0/1 lines into Grapheme, the sharpest edge in the package."""
        with pytest.raises(esolangs.ArgumentError, match="spells its bits"):
            esolangs.check_stdin("Grapheme", "0\n1\n")

    def test_it_catches_a_surplus_line(self) -> None:
        """Six lines into a three-input program answered the first three."""
        with pytest.raises(esolangs.ArgumentError, match="reads 3 line"):
            esolangs.check_stdin("brainfuck", "1\n1\n0\n0\n1\n1\n", "00010111")

    def test_it_catches_a_missing_line(self) -> None:
        """The direction that already errored at run time, now before it."""
        with pytest.raises(esolangs.ArgumentError, match="reads 3 line"):
            esolangs.check_stdin("brainfuck", "1\n0\n", "00010111")

    def test_it_catches_an_out_of_range_row_index(self) -> None:
        """What `run` could not check, because it does not know the arity."""
        with pytest.raises(esolangs.ArgumentError, match="out of range"):
            esolangs.check_stdin("Fargo", "8\n", "00010111")

    def test_it_catches_taglates_pad(self) -> None:
        """Its odd input count costs an extra line, and the shape says so."""
        esolangs.check_stdin(
            "Taglate",
            esolangs.encode_inputs("Taglate", [1, 0, 1], "00010111"),
            "00010111",
        )
        with pytest.raises(esolangs.ArgumentError):
            esolangs.check_stdin("Taglate", "1\n0\n1\n", "00010111")

    def test_it_refuses_a_language_with_no_stdin(self) -> None:
        """A template language reads none, so there is nothing to judge."""
        with pytest.raises(esolangs.ArgumentError, match="reads no stdin"):
            esolangs.check_stdin("Minifuck", "1\n0\n")

    def test_the_table_is_optional(self) -> None:
        """Shape and alphabet are checkable without knowing the arity."""
        esolangs.check_stdin("brainfuck", "1\n0\n")

    def test_a_non_string_stdin_is_named(self) -> None:
        """A caller who passes the bit list itself, which is an easy slip."""
        with pytest.raises(esolangs.ArgumentError, match="stdin must be a string"):
            esolangs.check_stdin("brainfuck", [1, 0], "0110")  # type: ignore[arg-type]

    def test_a_one_line_language_has_its_bits_counted(self) -> None:
        """Clockwise's underfeed is a shorter string, not a missing line.

        Undetectable from the run, which is why it stayed on the documented
        footgun list for three rounds -- but perfectly detectable *here*,
        because the table says how many bits that one line should hold.
        """
        esolangs.check_stdin("Clockwise", "101", "00010111")
        with pytest.raises(esolangs.ArgumentError, match="wants 3 bits"):
            esolangs.check_stdin("Clockwise", "10", "00010111")

    def test_the_closed_sets_are_exported(self) -> None:
        """A verifier branching on these should not spell a magic string."""
        modes = {
            str(esolangs.describe(n)["answer_mode"]) for n in esolangs.list_languages()
        }
        shapes = {
            str(esolangs.describe(n)["input_shape"]) for n in esolangs.list_languages()
        }
        assert modes <= set(esolangs.ANSWER_MODES)
        assert shapes <= set(esolangs.INPUT_SHAPES)


class TestRunSaysWhenStdinLooksWrong:
    """Silence was indistinguishable from correctness, from Python."""

    def test_a_surplus_line_is_warned_about(self) -> None:
        """Six lines into a three-input program answered the first three."""
        program = esolangs.generate("brainfuck", "00010111")
        with pytest.warns(UserWarning, match="read 3 of the 6 lines"):
            answer = esolangs.run("brainfuck", program, "1\n1\n0\n0\n1\n1\n", 10)
        # A warning, not a refusal: the run still happened and still answered.
        assert answer == "1"

    def test_the_wrong_alphabet_is_warned_about(self) -> None:
        """The same judgement `check_stdin` raises, rendered as advice."""
        program = esolangs.generate("Grapheme", "0110")
        with pytest.warns(UserWarning, match="spells its bits"):
            esolangs.run("Grapheme", program, "0\n1\n", 10)

    def test_the_documented_path_is_silent(self) -> None:
        """A warning that fires on correct input is worse than none."""
        import warnings

        noisy = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if facts["parameterized"]:
                continue
            program = esolangs.generate(name, "0110")
            if facts["answer_mode"] == "termination":
                continue
            stdin = esolangs.encode_inputs(name, [1, 0], "0110")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                esolangs.run(name, program, stdin, 20)
            if caught:
                noisy.append(f"{name}: {caught[0].message}")
        assert not noisy, "\n".join(noisy)

    def test_a_program_that_reads_nothing_is_not_warned_about(self) -> None:
        """Reading none of what it was given is not an arity mistake."""
        import warnings

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            esolangs.run("brainfuck", "+.", "1\n0\n", 10)
        assert not [c for c in caught if "lines supplied" in str(c.message)]

    def test_taking_a_value_from_past_the_end_is_warned_about(self) -> None:
        """The six that answer an underfed program now say they did.

        The signal is the *count of reads past the end*, not a guess from
        the supplied length: an underfeed supplies some input and runs off
        the end after it, which a ``supplied == 0`` test misses entirely.
        """
        for name in ("Circuit Diagram", "DINAC", "Flowchart", "S*bleq"):
            program = esolangs.generate(name, "10010110")
            short = esolangs.encode_inputs(name, [1, 0])
            with pytest.warns(UserWarning, match="past the end"):
                esolangs.run(name, program, short, 10)

    def test_forgetting_stdin_entirely_is_warned_about(self) -> None:
        """Fargo answered row 0 -- the starkest case, since nothing was fed."""
        with pytest.warns(UserWarning, match="past the end"):
            esolangs.run("Fargo", esolangs.generate("Fargo", "10010110"), "", 10)

    def test_a_language_whose_documented_stop_is_eof_is_not_warned_about(
        self,
    ) -> None:
        """Suffolk's programs end *by* running out of input.

        It halts rather than taking a value, so the warning is gated on
        ``eof_is_a_value`` -- counting the read alone warned about every
        correct Suffolk run there is, which is the false positive that
        makes a warning worth less than silence.
        """
        import warnings

        program = esolangs.generate("Suffolk", "0110")
        stdin = esolangs.encode_inputs("Suffolk", [1, 0], "0110")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assert esolangs.run("Suffolk", program, stdin, 20) == "1"
        assert not caught

    def test_no_language_warns_on_its_own_encoding(self) -> None:
        """The sweep that decides whether any of this is worth having."""
        import warnings

        noisy = []
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if facts["parameterized"] or facts["answer_mode"] == "termination":
                continue
            stdin = esolangs.encode_inputs(name, [1, 0], "0110")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                esolangs.run(name, esolangs.generate(name, "0110"), stdin, 20)
            if caught:
                noisy.append(f"{name}: {caught[0].message}")
        assert not noisy, "\n".join(noisy)


class TestInstantiateCanCheckProvenance:
    """A tag cannot survive a file, but a table can be compared against."""

    def test_a_hand_written_template_is_refused_given_the_table(self) -> None:
        """`"hello {X0}"` filled to `'hello [<'` and ran to nothing."""
        with pytest.raises(esolangs.TemplateError, match="is not the template"):
            esolangs.instantiate("Minifuck", "hello {X0}", [1], truth_table="01")

    def test_the_real_template_passes(self) -> None:
        """And still fills, and still answers its row."""
        template = esolangs.generate("Minifuck", "0110")
        program = esolangs.instantiate("Minifuck", template, [0, 1], truth_table="0110")
        assert (
            esolangs.read_answer("Minifuck", esolangs.run("Minifuck", program, "", 20))
            == "1"
        )

    def test_the_table_stays_optional(self) -> None:
        """Every existing caller passes three arguments."""
        template = esolangs.generate("Minifuck", "0110")
        assert esolangs.instantiate("Minifuck", template, [0, 1])


class TestSnapshotSaysItIsOpaque:
    """Its positions are not a schema and cannot be."""

    def test_the_docstring_says_so(self) -> None:
        """A reader asked what the fields were; there are no fields."""
        from esolangs.vm import _StepMachine

        doc = _StepMachine.snapshot.__doc__
        assert doc is not None
        assert "Opaque" in doc


class TestTheApiNameListsCannotDriftAgain:
    """Three rounds running, a reader found a public name in neither list.

    ``evaluate``/``verify`` were missing, then ``check_program``/``make_vm``,
    then ``encode_inputs``/``read_answer``/``check_stdin``.  Fixing the
    instance three times is what a test is for.
    """

    @staticmethod
    def _public_callables() -> set[str]:
        """The exported names that are functions a caller would call.

        ``inspect.isfunction`` rather than ``callable``: a ``Literal`` type
        alias like ``StopReason`` answers ``callable()`` truthfully enough
        to have been demanded of the README, which is not the point.
        """
        import inspect

        return {
            name
            for name in esolangs.__all__
            if inspect.isfunction(getattr(esolangs, name))
        }

    def test_the_readme_sentence_names_every_public_function(self) -> None:
        """The sentence that introduces the API has to introduce all of it."""
        readme = (pathlib.Path(__file__).parents[1] / "README.md").read_text()
        # The paragraph, not the first "." -- which lands inside
        # ``esolangs.run`` and made this pass on almost nothing.
        sentence = readme.split("The Python API is", 1)[1].split("\n\n", 1)[0]
        missing = sorted(n for n in self._public_callables() if n not in sentence)
        assert not missing, f"README's API sentence omits: {missing}"

    def test_the_module_docstring_names_every_public_function(self) -> None:
        """Same for the thing ``help(esolangs)`` shows first."""
        doc = esolangs.__doc__ or ""
        missing = sorted(n for n in self._public_callables() if n not in doc)
        assert not missing, f"esolangs.__doc__ omits: {missing}"


class TestDivergenceIsProvenNotWaitedOut:
    """A repeated state settles it exactly, and in milliseconds."""

    @pytest.mark.parametrize("name", ["123", "ArrowQueue", "Point Break"])
    @pytest.mark.parametrize("table", ["0110", "00011011"])
    def test_the_proven_answer_is_the_table(self, name: str, table: str) -> None:
        """The answers must be the ones the clock used to give, exactly."""
        assert esolangs.evaluate(name, table) == table

    def test_it_no_longer_costs_a_timeout_per_row(self) -> None:
        """It was five seconds per 1-row: twenty seconds for this call.

        Timed rather than asserted about, because "it is faster now" is the
        kind of claim that quietly stops being true.  The bound is loose --
        it is checking that the *clock* is no longer in the loop, not
        holding anything to a schedule.
        """
        import time

        start = time.monotonic()
        esolangs.evaluate("123", "0110")
        assert time.monotonic() - start < 5.0


class TestBoolsAreRefusedForAStatedReason:
    """ "must be 0 or 1" reads as wrong when you passed True, which is 1."""

    def test_the_message_says_why(self) -> None:
        """The exclusion is deliberate and the reason is a past wrong answer."""
        with pytest.raises(esolangs.ArgumentError, match="True == 1"):
            esolangs.encode_inputs("brainfuck", [True, False])


class TestUnknownLanguageAlwaysOffersANextStep:
    """A near miss suggested; a far one was a dead end."""

    def test_a_far_miss_names_the_listing_command(self) -> None:
        """Someone misremembering a name has nothing to be suggested."""
        with pytest.raises(esolangs.UnknownLanguageError, match="esolangs list"):
            esolangs.describe("Malbolge")

    def test_a_near_miss_still_suggests(self) -> None:
        """The better hint must win where there is one."""
        with pytest.raises(esolangs.UnknownLanguageError, match="did you mean"):
            esolangs.describe("Brainfck")


class TestTheWarningHasItsOwnClass:
    """So a sweep can escalate exactly these to errors."""

    def test_it_is_a_user_warning_subclass(self) -> None:
        """Existing ``UserWarning`` filters must keep working."""
        assert issubclass(esolangs.InputMismatchWarning, UserWarning)
        assert "InputMismatchWarning" in esolangs.__all__

    def test_run_raises_it_by_class(self) -> None:
        """Which is what makes ``filterwarnings("error", ...)`` targeted."""
        program = esolangs.generate("brainfuck", "00011011")
        with pytest.warns(esolangs.InputMismatchWarning):
            esolangs.run("brainfuck", program, "1\n1\n0\n0\n1\n1\n", 10)


class TestARowIndexNeverHasALeadingZero:
    """`0010` fed to a 16-row program parses as ten and answers row 10."""

    def test_a_bit_string_typed_as_an_index_is_caught(self) -> None:
        """No table needed: the leading zero alone decides it."""
        with pytest.raises(esolangs.ArgumentError, match="leading zero"):
            esolangs.check_stdin("Fargo", "0010\n")

    def test_the_message_gives_the_index_they_meant(self) -> None:
        """`0010` as bits is row 2, and saying so is the whole fix."""
        with pytest.raises(esolangs.ArgumentError, match="the index is 2"):
            esolangs.check_stdin("Fargo", "0010\n")

    def test_a_real_index_passes(self) -> None:
        """Including a single zero, which has no *leading* zero to speak of."""
        esolangs.check_stdin("Fargo", "0\n")
        esolangs.check_stdin("Fargo", "15\n")


class TestTheTerminationProofFallsBackToTheClock:
    """A cycle is not the only way to diverge; growth never repeats a state."""

    def test_the_proof_beats_even_a_millisecond_bound(self) -> None:
        """Which is the measurement, and also why the clock arm is untested.

        I expected a one-millisecond bound to force the fallback and assert
        the old "diverges" answer.  It does not: these programs revisit a
        state inside a hundred steps, so the cycle is proven before the
        clock can fire, and the right table comes back anyway.  The
        fallback is real -- unbounded growth never repeats a state -- but
        no table in this suite reaches it.
        """
        assert esolangs.evaluate("123", "0110", 0.001) == "0110"

    def test_the_answers_match_what_the_clock_used_to_give(self) -> None:
        """The proof must not have changed any verdict, only the cost."""
        for name in ("123", "ArrowQueue", "Point Break"):
            assert esolangs.evaluate(name, "0110") == "0110"


class TestATimeoutCannotKillTheProcess:
    """The long-running defect, and the second thing it turned into.

    A sub-millisecond ``timeout`` killed the interpreter outright about one
    run in three: no traceback, no exception, exit 142, which is SIGALRM's
    default disposition doing what it does.  Two attempts to close the race
    that delivers it failed, and the third worked by never restoring
    ``SIG_DFL`` -- a handler that does nothing cannot kill anything.

    That fix was wrong in a quieter way, and a later reader found it: the
    no-op stayed installed, so every alarm the *caller* set afterwards was
    swallowed, and a pending one was cancelled outright.  Taking someone
    else's signals is worse than a rare death at a bound nobody uses.

    So the disposition is restored exactly, the pending alarm is put back,
    and the bound that re-opens the race is refused instead.  Measured, with
    ``SIG_DFL`` genuinely restored: at 100 microseconds 19 of 20 processes
    hammering it died; at 1 millisecond, none in 4000 runs.  The floor is
    that measurement, not a taste.
    """

    def test_a_bound_too_short_to_service_is_refused(self) -> None:
        """The floor, which is what makes restoring the disposition safe."""
        with pytest.raises(esolangs.ArgumentError, match=r"at least 0\.001"):
            esolangs.run("brainfuck", "+.", "", 0.0001)

    def test_the_caller_gets_their_disposition_back(self) -> None:
        """Including ``SIG_DFL``, which the previous fix kept for itself."""
        import signal

        previous = signal.signal(signal.SIGALRM, signal.SIG_DFL)
        try:
            program = esolangs.generate("brainfuck", "0110")
            stdin = esolangs.encode_inputs("brainfuck", [0, 1], "0110")
            esolangs.run("brainfuck", program, stdin, 5)
            assert signal.getsignal(signal.SIGALRM) is signal.SIG_DFL
        finally:
            signal.signal(signal.SIGALRM, previous)

    def test_a_custom_handler_is_given_back_too(self) -> None:
        """The case that always worked, kept so the fix cannot regress it."""
        import signal

        def _mine(_signum: object, _frame: object) -> None:
            """A handler a caller might have installed."""

        previous = signal.signal(signal.SIGALRM, _mine)
        try:
            program = esolangs.generate("brainfuck", "0110")
            stdin = esolangs.encode_inputs("brainfuck", [0, 1], "0110")
            esolangs.run("brainfuck", program, stdin, 5)
            assert signal.getsignal(signal.SIGALRM) is _mine
        finally:
            signal.signal(signal.SIGALRM, previous)

    def test_the_timer_is_always_disarmed(self) -> None:
        """A timer left armed is the next run's stray alarm."""
        import signal

        program = esolangs.generate("brainfuck", "0110")
        stdin = esolangs.encode_inputs("brainfuck", [0, 1], "0110")
        for bound in (10, 0.001):
            with contextlib.suppress(esolangs.ExecutionTimeoutError):
                esolangs.run("brainfuck", program, stdin, bound)
            assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)

    @pytest.mark.slow
    def test_many_runs_at_the_floor_neither_die_nor_leak(self) -> None:
        """The stress the floor was chosen against, in process.

        A death here would take the whole test session with it, which is
        exactly the failure being guarded and makes it unmissable.
        """
        import signal

        program = esolangs.generate("brainfuck", "0110")
        stdin = esolangs.encode_inputs("brainfuck", [0, 1], "0110")
        previous = signal.signal(signal.SIGALRM, signal.SIG_DFL)
        try:
            for _ in range(400):
                with contextlib.suppress(esolangs.ExecutionTimeoutError):
                    esolangs.run("brainfuck", program, stdin, 0.001)
                assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
                assert signal.getsignal(signal.SIGALRM) is signal.SIG_DFL
        finally:
            signal.signal(signal.SIGALRM, previous)


class TestErrorsSurviveAProcessBoundary:
    """The library's commonest error could not come home from a worker."""

    def test_input_exhausted_round_trips(self) -> None:
        """It built its message in ``__init__``, so unpickling passed one arg.

        A worker raising it died, and the pool broke with
        ``BrokenProcessPool`` and no diagnostic -- for the error 43 of the
        52 stdin languages raise, in the parallel sweep this package is
        for.
        """
        import pickle

        program = esolangs.generate("brainfuck", "10010110")
        with pytest.raises(esolangs.InputExhaustedError) as caught:
            esolangs.run("brainfuck", program, "1\n0\n", 10)
        restored = pickle.loads(pickle.dumps(caught.value))
        assert str(restored) == str(caught.value)
        assert restored.reads == caught.value.reads
        assert restored.supplied == caught.value.supplied

    def test_unknown_language_does_not_grow_its_message(self) -> None:
        """It re-applied its prefix on every hop: "unknown language: " twice."""
        import pickle

        with pytest.raises(esolangs.UnknownLanguageError) as caught:
            esolangs.describe("nosuchlang")
        current: BaseException = caught.value
        for _ in range(3):
            current = pickle.loads(pickle.dumps(current))
        assert str(current) == str(caught.value)

    def test_every_error_class_round_trips(self) -> None:
        """The two above were found one at a time; this is the class."""
        import pickle

        raisers = [
            lambda: esolangs.describe("nosuchlang"),
            lambda: esolangs.generate("brainfuck", "011"),
            lambda: esolangs.encode_inputs("brainfuck", [2, 0]),
            lambda: esolangs.instantiate("brainfuck", "x", [0]),
            lambda: esolangs.run("brainfuck", None),  # type: ignore[arg-type]
            lambda: esolangs.run("brainfuck", "+[]", "", 0.01),
            lambda: esolangs.run(
                "brainfuck", esolangs.generate("brainfuck", "10010110"), "1\n0\n", 10
            ),
        ]
        for raise_it in raisers:
            with pytest.raises(esolangs.EsolangError) as caught:
                raise_it()
            restored = pickle.loads(pickle.dumps(caught.value))
            assert str(restored) == str(caught.value), type(caught.value).__name__


class TestTheCallersSignalsAreTheirOwn:
    """The fix for the death took the caller's SIGALRM hostage."""

    def test_a_pending_alarm_survives_a_timed_run(self) -> None:
        """Arming ours cancelled theirs, and nothing put it back."""
        import signal

        previous = signal.signal(signal.SIGALRM, lambda *_a: None)
        try:
            signal.alarm(30)
            program = esolangs.generate("brainfuck", "0110")
            stdin = esolangs.encode_inputs("brainfuck", [0, 1], "0110")
            esolangs.run("brainfuck", program, stdin, 5)
            remaining = signal.alarm(0)
            assert remaining > 0, "the caller's alarm was cancelled"
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, previous)

    def test_the_default_disposition_is_restored(self) -> None:
        """It was left as a no-op, which swallowed the caller's later alarms.

        Closing the death by never restoring ``SIG_DFL`` traded one bug for
        a quieter one: every alarm the caller set afterwards was ignored.
        """
        import signal

        previous = signal.signal(signal.SIGALRM, signal.SIG_DFL)
        try:
            program = esolangs.generate("brainfuck", "0110")
            stdin = esolangs.encode_inputs("brainfuck", [0, 1], "0110")
            esolangs.run("brainfuck", program, stdin, 5)
            assert signal.getsignal(signal.SIGALRM) is signal.SIG_DFL
        finally:
            signal.signal(signal.SIGALRM, previous)

    def test_a_bound_too_short_to_service_is_refused(self) -> None:
        """Measured: at 100us, 19 of 20 processes died; at 1ms, none of 4000."""
        with pytest.raises(esolangs.ArgumentError, match=r"at least 0\.001"):
            esolangs.run("brainfuck", "+.", "", 0.0001)

    def test_the_floor_applies_to_evaluate_too(self) -> None:
        """Its termination path never reaches ``run``, so it checked nothing.

        The same bound raised for sixty-six languages and was silently read
        as "diverges" for the other three, which returned a confident
        ``1111`` for XOR.
        """
        with pytest.raises(esolangs.ArgumentError, match=r"at least 0\.001"):
            esolangs.evaluate("123", "0110", 1e-06)


class TestEvaluateCanRunOffTheMainThread:
    """The wall-clock guard is a signal, and there was no way to opt out."""

    def test_an_explicit_none_means_unbounded(self) -> None:
        """As it does in ``run``; here the same word meant "use the default"."""
        import concurrent.futures as cf

        names = ["brainfuck", "Suffolk", "123", "A Painter Ant", "Fargo"]
        with cf.ThreadPoolExecutor(4) as pool:
            got = list(pool.map(lambda n: esolangs.verify(n, "0110", None), names))
        assert all(got), dict(zip(names, got, strict=True))

    def test_omitting_it_still_takes_the_defaults(self) -> None:
        """A sentinel, so adding the escape hatch broke no existing caller."""
        assert esolangs.evaluate("123", "0110") == "0110"


class TestAPaintersMarkMustBeInAGrid:
    """Its pattern was ``([o@])``, so any stray ``o`` read as a zero."""

    @pytest.mark.parametrize("junk", ["nonsense", "hello world", "no such thing"])
    def test_garbage_is_refused(self, junk: str) -> None:
        """It was the one language that read a crash message as an answer."""
        with pytest.raises(esolangs.ProgramError):
            esolangs.read_answer("A Painter Ant", junk)

    def test_a_real_grid_still_reads(self) -> None:
        """The check is worth nothing if it costs the actual answers."""
        assert esolangs.evaluate("A Painter Ant", "0110") == "0110"


class TestTheDebuggerMirrorsSnapshot:
    """Reaching through ``.vm`` is what the mirrors exist to avoid."""

    def test_it_matches_the_wrapped_machine(self) -> None:
        """And is the thing a caller most wants: a repeated state."""
        program = esolangs.generate("brainfuck", "0110")
        stdin = esolangs.encode_inputs("brainfuck", [0, 1], "0110")
        debugger = esolangs.make_debugger("brainfuck", program, stdin)
        assert debugger.snapshot() == debugger.vm.snapshot()
        before = debugger.snapshot()
        debugger.step()
        assert debugger.snapshot() != before


class TestAnInterpreterLimitIsStillAnEsolangError:
    """Qoibl's interpreter recurses, and Python's stack is finite."""

    @staticmethod
    def _parity(n: int) -> str:
        """Return the parity table of arity ``n`` -- reliably a hard one."""
        return "".join(str(bin(i).count("1") % 2) for i in range(2**n))

    @pytest.mark.slow
    def test_a_recursion_error_does_not_escape(self) -> None:
        """It was the one exception in the package that was not ours.

        The package makes exactly one promise about errors -- that every
        deliberate failure derives from ``EsolangError`` -- and a sweep
        written to it crashed here.
        """
        with pytest.raises(esolangs.EsolangError) as caught:
            esolangs.verify("Qoibl", self._parity(6))
        assert isinstance(caught.value, esolangs.InterpreterLimitError)
        assert "recursed deeper" in str(caught.value)

    def test_it_is_a_halt_error(self) -> None:
        """The run ended abnormally, which is what that base means."""
        assert issubclass(esolangs.InterpreterLimitError, esolangs.HaltError)
        assert "InterpreterLimitError" in esolangs.__all__

    def test_it_is_not_a_generator_cap(self) -> None:
        """A cap declines to build; this built and could not be run."""
        assert not issubclass(
            esolangs.InterpreterLimitError, esolangs.GeneratorCapError
        )


class TestBothWidthAwareGeneratorsCanOverrun:
    """The docstring named LaserFuck; Streetcode is the worse of the two."""

    @staticmethod
    def _overruns(name: str, table: str) -> tuple[int, int]:
        """Return how many widths overran, and by the worst margin."""
        counted = [
            max(len(line) for line in esolangs.generate(name, table, w).splitlines())
            - w
            for w in range(8, 124, 4)
        ]
        over = [margin for margin in counted if margin > 0]
        return len(over), max(over, default=0)

    def test_both_width_aware_generators_can_overrun(self) -> None:
        """Which is the claim; the numbers live here rather than in prose."""
        for name in ("LaserFuck", "Streetcode"):
            widths, worst = self._overruns(name, "10010110")
            assert widths > 0, f"{name} never overran"
            assert worst > 0

    def test_streetcode_is_the_worse_of_the_two(self) -> None:
        """The specific thing the docstring got backwards."""
        laser_widths, laser_worst = self._overruns("LaserFuck", "10010110")
        street_widths, street_worst = self._overruns("Streetcode", "10010110")
        assert street_widths > laser_widths
        assert street_worst > laser_worst

    def test_they_are_exactly_the_width_aware_pair(self) -> None:
        """So a third one appearing makes the sentence above wrong loudly."""
        aware = {
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["width_aware"]
        }
        assert aware == {"LaserFuck", "Streetcode"}


class TestTheCheckProgramExampleRuns:
    """Its inline one-liner raised for two of the three languages it names."""

    @pytest.mark.parametrize("name", ["CV(N)(C)", "Grapheme", "NoComment"])
    def test_reading_a_committed_example_works(self, name: str) -> None:
        """The newline fix is real; the snippet showing it was not runnable."""
        import pathlib as _pathlib

        path = _pathlib.Path(str(esolangs.describe(name)["examples"][0]))
        facts = esolangs.describe(name)
        stdin = "" if not facts["reads_input"] else esolangs.encode_inputs(name, [0, 1])
        assert esolangs.run(name, path, stdin, 20) is not None


class TestEvaluateNoLongerClaimsToPayTheTimeout:
    """Its docstring and ``Debugger.snapshot``'s disagreed about the same thing."""

    def test_a_termination_table_returns_far_inside_the_bound(self) -> None:
        """Five seconds per 1-row would be twenty for this table."""
        import time

        start = time.monotonic()
        assert esolangs.evaluate("123", "0110") == "0110"
        assert time.monotonic() - start < 2.0

    def test_the_docstring_says_the_proof_is_the_mechanism(self) -> None:
        """Prose, checked, because it was prose that had gone stale."""
        doc = esolangs.evaluate.__doc__
        assert doc is not None
        # Not a search for the old phrase: the correction quotes it in
        # order to retract it, so an absence test fails on the fix.  What
        # has to be there is the mechanism and the denial.
        assert "repeated machine state" in doc
        assert "do not pay it" in doc


class TestDescribeDocumentsWhatItReturns:
    """A key you get back should be findable in the docstring you read.

    ``width_effect`` was the case that prompted this: it was explained in
    ``generate --help`` and in a *private* function's docstring, so a
    library reader running ``help(esolangs.describe)`` got a long paragraph
    about ``width_aware`` and not one word about the key that superseded
    it.  Four more keys were described in prose -- "the state model", "its
    example programs" -- which reads well and is invisible to anyone
    grepping for a key they just got back from the dict.
    """

    def test_every_key_is_named_in_the_docstring(self) -> None:
        """Naming, not explaining: a grep for the key has to land somewhere."""
        doc = esolangs.describe.__doc__ or ""
        missing = sorted(k for k in esolangs.describe("brainfuck") if k not in doc)
        assert not missing, (
            f"describe() returns keys its docstring never names: {missing}"
        )

    def test_every_language_returns_the_same_keys(self) -> None:
        """The guard above reads one language, so the keys must not vary."""
        keys = {frozenset(esolangs.describe(n)) for n in esolangs.list_languages()}
        assert len(keys) == 1


class TestTheTwoWidthKeysCannotDrift:
    """``width_aware`` is exactly ``width_effect == "layout"``.

    It used to be a second copy of the expression ``_width_effect``
    evaluates, so the two could have come to disagree about one language
    with nothing to catch it.  It is derived now, and this is what says so.
    """

    def test_width_aware_is_the_layout_case(self) -> None:
        """Every language, not a sample: the old duplication was per-language."""
        for name in esolangs.list_languages():
            described = esolangs.describe(name)
            assert described["width_aware"] == (
                described["width_effect"] == "layout"
            ), name

    def test_all_three_effects_are_represented(self) -> None:
        """A guard over a field with one value in practice guards nothing.

        The counts are here because they are the reason ``width_aware``
        was not enough on its own: it is ``False`` for both of the two
        large groups, which is what a reader ran into.
        """
        counts: dict[str, int] = {}
        for name in esolangs.list_languages():
            effect = str(esolangs.describe(name)["width_effect"])
            counts[effect] = counts.get(effect, 0) + 1
        assert counts == {"none": 38, "wrap": 29, "layout": 2}


class TestEveryDumpSaysWhereTheAnswerIs:
    """A dump prints the whole final state, so "where" is the question.

    For ``answer_mode == "output"`` the answer simply *is* the output and
    53 languages rightly carry neither a pattern nor a note.  For a dump it
    is a real gap, and Bitdeque was the one dump with neither -- the reader
    who found it could not tell whether that meant "nothing to say" or
    "nobody wrote it down".  It was the former, and now it says so.
    """

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

    def test_bitdeques_note_is_true(self) -> None:
        """It claims the whole dump is the answer bit.  Check that, do not trust it.

        A note is prose, and prose is the thing in this package that goes
        stale; the claim is cheap to run, so it gets run.
        """
        note = str(esolangs.describe("Bitdeque")["answer_convention"])
        assert "the whole dump is the answer" in note
        template = esolangs.generate("Bitdeque", "0110")
        for combo in range(4):
            bits = [(combo >> (1 - i)) & 1 for i in range(2)]
            program = esolangs.instantiate("Bitdeque", template, bits)
            dump = esolangs.run("Bitdeque", program, "", timeout=10)
            assert dump == "0110"[combo], bits
            assert len(dump) == 1, dump


class TestABadStdinIsAnArgumentFault:
    """Four entry points filed it as a *program* fault, and one did not.

    ``ProgramError`` says "a program could not be loaded: it is malformed
    for its language".  The stdin is not the program.  Both derive from
    ``EsolangError`` so a generic handler always worked, but the taxonomy
    is the thing this package sells, and here it disagreed with itself.
    """

    @pytest.mark.parametrize(
        "call",
        [
            lambda: esolangs.run("brainfuck", ",.", b"0\n"),
            lambda: esolangs.check_program("brainfuck", ",.", b"0\n"),
            lambda: esolangs.make_vm("brainfuck", ",.", b"0\n"),
            lambda: esolangs.make_debugger("brainfuck", ",.", b"0\n"),
            lambda: esolangs.check_stdin("brainfuck", b"0\n"),
        ],
    )
    def test_every_entry_point_agrees(self, call: object) -> None:
        """One fault, one class -- ``except ArgumentError`` has to cover all five."""
        with pytest.raises(esolangs.ArgumentError, match="stdin must be a string"):
            call()  # type: ignore[operator]

    def test_a_bad_program_is_still_a_program_error(self) -> None:
        """The change must not blur the distinction the other way."""
        with pytest.raises(esolangs.ProgramError, match="program must be a string"):
            esolangs.run("brainfuck", 42, "")  # type: ignore[arg-type]


class TestASurroundingSpaceResolves:
    """67 of 69 names already tolerated one, and the two that did not.

    ``canonical_id`` collapses runs of non-alphanumerics and strips the
    result, so a stray space fell out for almost every name.  The override
    table is an exact lookup, though, so the two names needing an override
    were exactly the two that broke -- and ``"CV(N)(C) "`` came back as
    ``did you mean CV(N)(C)?``, an invisible diff with no way forward.
    """

    @pytest.mark.parametrize("pad", [" {}", "{} ", " {} ", "\t{}\n"])
    def test_every_language_tolerates_surrounding_space(self, pad: str) -> None:
        """All 69, because the two that failed were not the obvious two."""
        for name in esolangs.list_languages():
            assert esolangs.describe(pad.format(name))["name"] == name

    @pytest.mark.parametrize("name", ["%^2^-1", "CV(N)(C)"])
    def test_the_two_override_names_specifically(self, name: str) -> None:
        """Named, so a future override cannot quietly reintroduce the gap."""
        assert esolangs.describe(f" {name} ")["name"] == name

    def test_internal_spacing_is_still_normalized(self) -> None:
        """The strip must not have replaced the rule that was already working."""
        assert esolangs.describe("Home  Row")["name"] == "Home Row"


class TestAnUnknownNameIsShownReadably:
    """A bare rendering can be a lie, and was for two shapes of input."""

    def test_an_empty_name_is_not_a_hole_in_a_sentence(self) -> None:
        """It read ``unknown language: ; `esolangs list` shows all of them``."""
        with pytest.raises(esolangs.UnknownLanguageError, match="unknown language: ''"):
            esolangs.describe("")

    def test_an_unprintable_name_is_quoted(self) -> None:
        """Otherwise the message renders the control character and lies."""
        with pytest.raises(esolangs.UnknownLanguageError) as caught:
            esolangs.describe("brain\x00fuck")
        assert "\\x00" in str(caught.value)

    def test_an_ordinary_miss_stays_unquoted(self) -> None:
        """Quoting every miss to cover the rare one makes the common case worse."""
        with pytest.raises(
            esolangs.UnknownLanguageError, match="unknown language: zzzz"
        ):
            esolangs.describe("zzzz")


class TestATableLengthNamesTheNearestLegalOnes:
    """The rule without the arithmetic, on the likeliest first error."""

    @pytest.mark.parametrize(
        ("table", "expected"),
        [
            ("0" * 3, "3 is between 2 (1 input) and 4 (2 inputs)"),
            ("0" * 6, "6 is between 4 (2 inputs) and 8 (3 inputs)"),
            ("0" * 100, "100 is between 64 (6 inputs) and 128 (7 inputs)"),
        ],
    )
    def test_the_brackets_are_named(self, table: str, expected: str) -> None:
        """And singular where it should be: "1 input", not "1 inputs"."""
        with pytest.raises(esolangs.TruthTableError, match=re.escape(expected)):
            esolangs.generate("brainfuck", table)

    def test_an_empty_table_gets_no_brackets(self) -> None:
        """``2 ** -1`` is 0.5, so the arithmetic does not apply to nothing."""
        with pytest.raises(esolangs.TruthTableError) as caught:
            esolangs.generate("brainfuck", "")
        assert "is between" not in str(caught.value)

    def test_the_brackets_are_actually_legal_lengths(self) -> None:
        """The message would be worse than none if it named an unusable size."""
        with pytest.raises(esolangs.TruthTableError) as caught:
            esolangs.generate("brainfuck", "0" * 6)
        for length in (4, 8):
            assert f"{length} (" in str(caught.value)
            esolangs.generate("brainfuck", "0" * length)  # so it builds


class TestFillingSomethingWithNoSlots:
    """ "0 input slots" is true and answers a question nobody asked."""

    def test_a_plain_program_says_it_is_not_a_template(self) -> None:
        """The mistake is "this is not a template", not a count of zero."""
        with pytest.raises(
            esolangs.TemplateError, match=re.escape("no {Xi} slots to fill")
        ):
            esolangs.instantiate("Minifuck", "abc", [1, 0])

    def test_filling_twice_says_the_same_thing(self) -> None:
        """The other way to get here, and it looks identical from inside."""
        template = esolangs.generate("Minifuck", "0110")
        filled = esolangs.instantiate("Minifuck", template, [1, 0])
        with pytest.raises(esolangs.TemplateError, match="already been applied"):
            esolangs.instantiate("Minifuck", filled, [1, 0])

    def test_a_real_slot_mismatch_still_counts(self) -> None:
        """The count is the right answer when there *are* slots."""
        template = esolangs.generate("Minifuck", "0110")
        with pytest.raises(esolangs.TemplateError, match="2 input slots"):
            esolangs.instantiate("Minifuck", template, [1, 0, 1])


class TestASuggestionIsWorthLessThanSilence:
    """0.6 offered ``Sophie`` for ``nope``.

    A wrong guess is worse than none: it sends the reader off to check a
    language they never meant.  0.65 is the lowest cutoff that suggests
    nothing for any of the junk below, and it rescues exactly as many real
    typos as 0.6 did -- 291 of 298 single-edit slips across the 69 names.
    0.7 starts costing rescues.

    The numbers are recomputed below rather than quoted, so the constant
    cannot drift away from the reason it has its value.
    """

    #: Single-edit slips of a real name, as a person makes them.
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

    _JUNK = ("nope", "zzzz", "xyz", "qqqqqq", "hello", "python", "asdf", "foo")

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
        """The trade, recomputed: 0.6 costs junk and 0.7 costs rescues.

        Without this the constant is a number somebody once measured, and
        the next person to nudge it has nothing to nudge it against.
        """
        shipped = self._score(SUGGESTION_CUTOFF)
        assert shipped[2] == 0, "the shipped cutoff offers a guess for junk"
        # Lower: the same rescues, but junk comes back.  This is the
        # positive control -- without it the cutoff could be doing nothing.
        lower = self._score(0.6)
        assert lower[0] == shipped[0]
        assert lower[2] > 0
        # Higher: no junk either, but it starts costing real rescues.
        assert self._score(0.7)[0] < shipped[0]

    @pytest.mark.parametrize(
        "word", ["nope", "zzzz", "xyz", "qqqqqq", "hello", "python", "asdf", "foo"]
    )
    def test_a_word_that_is_not_close_gets_no_guess(self, word: str) -> None:
        """It gets the command that lists them, which is the honest answer."""
        with pytest.raises(esolangs.UnknownLanguageError) as caught:
            esolangs.describe(word)
        assert "did you mean" not in str(caught.value)
        assert "`esolangs list` shows all of them" in str(caught.value)

    @pytest.mark.parametrize(
        ("typo", "wanted"),
        [
            ("Brainfck", "brainfuck"),
            ("brainfuk", "brainfuck"),
            ("Streetcod", "Streetcode"),
            ("Minifuk", "Minifuck"),
            ("Sofie", "Sophie"),
            ("Sufolk", "Suffolk"),
        ],
    )
    def test_a_real_typo_is_still_rescued(self, typo: str, wanted: str) -> None:
        """The half of the trade that raising a cutoff can quietly cost."""
        with pytest.raises(esolangs.UnknownLanguageError) as caught:
            esolangs.describe(typo)
        assert wanted in str(caught.value)

    def test_the_cli_shares_the_number(self) -> None:
        """Its docstring promised the same cutoff while keeping its own copy."""
        assert cli._did_you_mean("nope", esolangs.list_languages()) == ""  # noqa: SLF001
        assert "--width" in cli._did_you_mean("--wdith", ["--width", "--bits"])  # noqa: SLF001


class TestReadAnswerExplainsInWords:
    """The regex was the whole explanation for the two pattern languages.

    Right for a maintainer, nothing at all for a reader wondering where the
    answer was meant to be -- and the plain-language note already existed on
    ``describe``.  The note leads now and the pattern follows in brackets,
    so neither reader loses.
    """

    @pytest.mark.parametrize("name", ["A Painter Ant", "RAM0"])
    def test_the_note_leads_and_the_pattern_follows(self, name: str) -> None:
        """Both halves, in that order."""
        with pytest.raises(esolangs.ProgramError) as caught:
            esolangs.read_answer(name, "garbage")
        message = str(caught.value)
        note = str(esolangs.describe(name)["answer_convention"])
        pattern = str(esolangs.describe(name)["answer_pattern"])
        assert note in message
        # The pattern is rendered with !r, so a backslash in it is doubled.
        assert repr(pattern) in message
        assert message.index(note) < message.index(repr(pattern))

    def test_a_plain_language_is_unchanged(self) -> None:
        """No pattern, no note, and nothing to add -- it was already clear."""
        with pytest.raises(esolangs.ProgramError) as caught:
            esolangs.read_answer("brainfuck", "garbage")
        assert "as the last character" in str(caught.value)
        assert "matched with" not in str(caught.value)

    def test_every_dump_language_says_something_in_words(self) -> None:
        """The general claim, not the two cases that prompted it.

        Writing this is what caught the narrow first fix: only the two
        *pattern* languages got the note, and Back, Minsky Swap and
        LaserFuck dump their state while being read by last character --
        so they got "as the last character", a true account of the
        mechanism and no account of where the answer lives.
        """
        for name in esolangs.list_languages():
            facts = esolangs.describe(name)
            if facts["answer_mode"] != "dump":
                continue
            with pytest.raises(esolangs.ProgramError) as caught:
                esolangs.read_answer(name, "garbage")
            note = facts["answer_convention"]
            assert note is None or str(note) in str(caught.value), name
