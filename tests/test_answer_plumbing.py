"""The plumbing between a truth table and the answer bit a program prints.

What encode_inputs, instantiate, read_answer and evaluate promise, and that
the prose in the README and the docstrings still matches the data.  Stdin
judgement and the refusals have their own modules.
"""

from __future__ import annotations

import pathlib
import re

import pytest

import esolangs
from esolangs import cli
from esolangs.cli import HELP

ROOT = pathlib.Path(__file__).parents[1]


README = (ROOT / "README.md").read_text()


USAGE_DOC = ROOT / "docs" / "usage.md"


#: The bit vector ``docs/usage.md``'s stdin table is rendered for; it has to
#: match the generator's ``_SAMPLE_BITS`` or the table cannot be compared.
_SAMPLE_BITS = [1, 0, 1]


#: How each shape may *not* be described, as a regex over the prose.  Only
#: the negative direction is regex-matched: a document that states one of
#: these about a language with a different shape is wrong, whatever else it
#: says.  Nothing here obliges a document to contain any of it.
_SHAPE_PROSE = {
    "one_line": r"(all |every |them all )?(bits? )?.{0,12}on one line",
    "row_index": r"row index as (one|a single) decimal number|row index as one decimal",
    "line_per_bit_padded": r"pads an odd input count with a leading zero",
}


def _every_document() -> dict[str, str]:
    """Return every document a reader could follow, keyed by where it is."""
    found = {"README.md": README, "usage": cli.USAGE}
    for name, text in HELP.items():
        found[f"{name} --help"] = text
    for doc in sorted((ROOT / "docs").rglob("*.md")):
        found[str(doc.relative_to(ROOT))] = doc.read_text()
    return found


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

    def test_the_reference_table_is_the_encoders_own_output(self) -> None:
        """The positive half, as data: every cell is what ``encode_inputs`` returns.

        Parsed back out of the rendered Markdown rather than compared to the
        renderer, so a table that was generated and then hand-edited fails
        here and not only in the sync test.
        """
        table = USAGE_DOC.read_text().split("<!-- INPUT-SHAPES:START -->")[1]
        rows = {}
        for line in table.splitlines():
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) == 4 and cells[0] in esolangs.list_languages():
                rows[cells[0]] = (cells[1], cells[3])

        expected = {}
        for name in esolangs.list_languages():
            record = esolangs.describe(name)
            if not record["reads_input"]:
                continue
            shape = record["input_shape"]
            alphabet = tuple(record["input_encoding"])
            if shape == "line_per_bit" and alphabet == ("0", "1"):
                continue
            stdin = esolangs.encode_inputs(name, _SAMPLE_BITS)
            expected[name] = (f"`{shape}`", f"`{stdin!r}`")

        assert rows == expected

    @pytest.mark.parametrize("document", sorted(_every_document()))
    def test_no_document_states_a_shape_a_language_does_not_have(
        self, document: str
    ) -> None:
        """The negative half, over every document rather than three.

        "Clockwise and Fargo want them all on one line" names Fargo in a
        clause matching ``one_line``, which is Clockwise's shape.  The
        positive half could never catch that, because the same documents
        also state Fargo's real shape somewhere else.
        """
        # Whitespace collapsed first: these documents are hard-wrapped, so a
        # newline lands in the middle of the phrase being matched.
        text = re.sub(r"\s+", " ", _every_document()[document])
        for name in esolangs.list_languages():
            shape = str(esolangs.describe(name)["input_shape"])
            naming = [s for s in re.split(r"(?<=[.,;])\s+", text) if name in s]
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
        assert "$$" in template


class TestATemplateCarriesItsSetters:
    """The conventions live on the template object, not on every caller.

    ``generate`` hands the template one ``(zero, one)`` pair per input, and
    the constructor refuses unequal widths and slots out of order, so a
    generator cannot leak a bit through the program's length or misname an
    input without failing at the point the template is made.
    """

    def test_every_parameterized_template_carries_equal_width_pairs(self) -> None:
        for name in esolangs.list_languages():
            if not esolangs.describe(name)["parameterized"]:
                continue
            template = esolangs.generate(name, "0110")
            pairs = template.setters
            assert pairs is not None, name
            assert len(pairs) == 2, name
            assert all(len(zero) == len(one) for zero, one in pairs), name

    def test_a_reading_language_has_no_setters(self) -> None:
        assert getattr(esolangs.generate("brainfuck", "0110"), "setters", None) is None

    def test_a_uniform_example_derives_its_setters_from_its_pair(self) -> None:
        """Every embedded example carries one pair and derives from it."""
        from esolangs.tools.examples import BOOLEAN_EXAMPLES, _embedded, uniform

        embedded = [e for e in BOOLEAN_EXAMPLES.values() if e.setters is not None]
        uniform_ones = [e for e in embedded if e.pair is not None]
        assert uniform_ones == embedded
        for example in uniform_ones:
            assert example.setters("", 3) == uniform(example.pair)("", 3)
        with pytest.raises(TypeError, match="exactly one"):
            _embedded(
                esolangs.generate, "x", pair=("a", "b"), setters=uniform(("a", "b"))
            )
        with pytest.raises(TypeError, match="exactly one"):
            _embedded(esolangs.generate, "x")
        # A pair-only call derives its setters; the import-time examples are
        # not always captured by the coverage tracer, so exercise it here.
        derived = _embedded(esolangs.generate, "x", pair=("a", "b"))
        assert derived.pair == ("a", "b")
        # And a setters-only call must not try to derive them.
        explicit = _embedded(esolangs.generate, "x", setters=uniform(("a", "b")))
        assert explicit.setters is not None

    def test_unequal_widths_are_refused(self) -> None:
        from esolangs.tagged import _Template

        with pytest.raises(ValueError, match="differ in width"):
            _Template("$", "Minifuck", setters=[("x", "xx")])

    def test_runs_that_do_not_fit_the_setters_are_refused(self) -> None:
        from esolangs.tagged import _Template

        with pytest.raises(ValueError, match="shorter than its setter width"):
            _Template("a$b$$", "Minifuck", setters=[("aa", "bb"), ("c", "d")])
        with pytest.raises(ValueError, match="belongs to no input"):
            _Template("a$$b$", "Minifuck", setters=[("aa", "bb")])
        with pytest.raises(ValueError, match="1 run"):
            _Template("a$$b", "Minifuck", setters=[("aa", "bb"), ("c", "d")])

    def test_a_fill_with_the_wrong_number_of_bits_is_refused(self) -> None:
        from esolangs.tools.helpers import fill_runs

        with pytest.raises(ValueError, match="expected 2 bits"):
            fill_runs("$$", "$", (("a", "b"), ("c", "d")), [1])

    def test_the_runs_pass_through_render_and_fill_by_width(self) -> None:
        """Run-form output is the template; marks are asked for by a wrapper."""
        from esolangs.tools.examples import _fill_from
        from esolangs.tools.helpers import mark, render

        pairs = (("xx", "yy"), ("p", "q"))
        assert render("a$$$b", "$", pairs) == "a$$$b"
        assert render("a$$$b", None, pairs) == "a" + mark(0) * 2 + mark(1) + "b"
        fill = _fill_from(lambda _template, n: pairs[:n])
        assert fill("a$$$b", [1, 0]) == "ayypb"

    def test_a_zero_width_setter_has_an_empty_run(self) -> None:
        """An input spelled as nothing on both branches fills to nothing."""
        from esolangs.tools.helpers import fill_runs, runs

        pairs = (("", ""), ("xx", "yy"), ("", ""))
        assert runs("a$$b", "$", pairs) == [(0, 0), (1, 3), (3, 3)]
        assert fill_runs("a$$b", "$", pairs, [1, 0, 1]) == "axxb"
        assert fill_runs("a$$b", "$", pairs, [0, 1, 0]) == "ayyb"

    def test_adjacent_inputs_need_no_separator(self) -> None:
        from esolangs.tagged import _Template

        template = _Template("a$$$b", "Minifuck", setters=[("xx", "yy"), ("p", "q")])
        assert template.fill([1, 0]) == "ayypb"
        assert template.fill([0, 1]) == "axxqb"

    def test_the_template_is_the_shape_of_every_program(self) -> None:
        """Every run is as long as its setter, so filling moves no character."""
        from esolangs.registry import template_body

        for name in ("Minifuck", "Bitdeque", "Crement"):
            template = esolangs.generate(name, "0110")
            shape = len(template_body(esolangs.describe(name)["id"], template))
            for bits in ([0, 0], [0, 1], [1, 0], [1, 1]):
                assert len(esolangs.instantiate(name, template, bits)) == shape

    def test_a_plain_string_is_filled_by_recovering_its_setters(self) -> None:
        for name in ("Minifuck", "Bitdeque", "A Painter Ant"):
            template = esolangs.generate(name, "0110")
            assert esolangs.instantiate(name, str(template), [1, 0]) == (
                esolangs.instantiate(name, template, [1, 0])
            )
        with pytest.raises(esolangs.TemplateError, match="not a Minifuck template"):
            esolangs.instantiate("Minifuck", "abc$$$", [1, 0])

    def test_the_setters_survive_a_width_and_a_pickle(self) -> None:
        import pickle

        template = esolangs.generate("Minifuck", "0110", 20)
        assert template.setters == esolangs.generate("Minifuck", "0110").setters
        copied = pickle.loads(pickle.dumps(template))
        assert copied.setters == template.setters
        assert copied.char == template.char


class TestAProgramKnowsWhoseItIs:
    """A generated program run under another language is refused at the door.

    Most interpreters are permissive enough to run foreign text as no-ops and
    answer, so the mistake is not a syntax error.  The tag is the same
    device the template carries, and as permissive: a plain string is
    accepted unchecked.
    """

    def test_a_foreign_program_is_refused_by_run(self) -> None:
        program = esolangs.generate("brainfuck", "0110")
        with pytest.raises(esolangs.ProgramError, match="generated for brainfuck"):
            esolangs.run("Minsky Swap", program)

    def test_a_foreign_program_is_refused_by_make_vm(self) -> None:
        program = esolangs.generate("brainfuck", "0110")
        with pytest.raises(esolangs.ProgramError, match="generated for brainfuck"):
            esolangs.make_vm("Minsky Swap", program, "")

    def test_a_filled_template_carries_its_language(self) -> None:
        template = esolangs.generate("Minifuck", "0110")
        program = esolangs.instantiate("Minifuck", template, [0, 1])
        assert getattr(program, "language", None) == "Minifuck"
        with pytest.raises(esolangs.ProgramError, match="generated for Minifuck"):
            esolangs.run("brainfuck", program)

    def test_its_own_language_still_runs_it(self) -> None:
        program = esolangs.generate("brainfuck", "0110")
        out = esolangs.run(
            "brainfuck", program, esolangs.encode_inputs("brainfuck", [0, 1])
        )
        assert esolangs.read_answer("brainfuck", out) == "1"

    def test_the_name_is_resolved_before_it_is_compared(self) -> None:
        program = esolangs.generate("BRAINFUCK", "0110")
        assert esolangs.run(
            "brainfuck", program, esolangs.encode_inputs("brainfuck", [0, 1])
        )

    def test_a_plain_string_is_accepted_unchecked(self) -> None:
        program = str(esolangs.generate("brainfuck", "0110"))
        assert getattr(program, "language", None) is None
        assert esolangs.run(
            "brainfuck", program, esolangs.encode_inputs("brainfuck", [0, 1])
        )

    def test_a_program_is_still_a_string_everywhere_else(self) -> None:
        import json
        import pickle

        program = esolangs.generate("brainfuck", "0110")
        assert isinstance(program, str)
        assert program == str(program)
        assert json.dumps(program) == json.dumps(str(program))
        copied = pickle.loads(pickle.dumps(program))
        assert copied == program
        assert getattr(copied, "language", None) == "brainfuck"
        template = pickle.loads(pickle.dumps(esolangs.generate("Minifuck", "0110", 20)))
        assert template == esolangs.generate("Minifuck", "0110", 20)
        assert template.replace("\n", "") == esolangs.generate("Minifuck", "0110")

    def test_a_width_keeps_the_tag(self) -> None:
        program = esolangs.generate("brainfuck", "0110", 20)
        assert getattr(program, "language", None) == "brainfuck"


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
        """A chdir away it was ``cannot read examples/brainfuck.txt``."""
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
        """60/60, through the public function rather than a local copy."""
        failed = [
            n
            for n in esolangs.list_languages()
            if esolangs.describe(n)["boolean_generator"]
            and not esolangs.verify(n, "0110")
        ]
        assert not failed


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
            if not facts["boolean_generator"]:
                continue
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
    """``run`` promised an exception for every language.  Most give it.

    A three-input program fed two bits: most raise, and six take the
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
            if not facts["boolean_generator"]:
                continue
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
            if esolangs.describe(name)["boolean_generator"]
            and not esolangs.describe(name)["parameterized"]
            and self._underfed(name)[0] == "raised"
        )
        # 41 of the 48 that read stdin, measured.  Pinned exactly, so that a change
        # which quietly moves a language out of the norm shows up here rather
        # than in a docstring nobody re-derives.
        assert raised == 41

    def test_the_trait_is_reported_by_describe(self) -> None:
        """A caller must be able to learn this without underfeeding one."""
        assert esolangs.describe("Flowchart")["eof_is_a_value"] is True
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


class TestBreakAtNamesTheKindNotTheValue:
    """It said "ip is 0" where it meant "ip is an index"."""

    def test_the_message_describes_the_kind(self) -> None:
        """A reader cannot generalize from one position's value."""
        program = esolangs.generate("brainfuck", "0110")
        debugger = esolangs.make_debugger("brainfuck", program, "0\n1\n")
        with pytest.raises(esolangs.ArgumentError, match="is an index"):
            debugger.break_at((1, 2))


class TestInstantiateCanCheckProvenance:
    """A tag cannot survive a file, but a table can be compared against."""

    def test_a_hand_written_template_is_refused_given_the_table(self) -> None:
        """`"hello $$"` filled to `'hello [<'` and ran to nothing."""
        with pytest.raises(esolangs.TemplateError, match="is not the template"):
            esolangs.instantiate("Minifuck", "hello $$", [1], truth_table="01")

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

    def test_the_api_reference_lists_every_public_function(self) -> None:
        """The reference has to introduce all of it -- as a list, not a sentence.

        This was "the README's API sentence names every function", which is
        what produced a thirteen-name run-on on the front page: the gate
        demanded one paragraph, so one paragraph is what got written.  A
        generated list carries the same guarantee per line.
        """
        listed = USAGE_DOC.read_text().split("<!-- PUBLIC-API:START -->", 1)[1]
        listed = listed.split("<!-- PUBLIC-API:END -->", 1)[0]
        entries = {
            line.split("`")[1].removeprefix("esolangs.")
            for line in listed.splitlines()
            if line.startswith("- `esolangs.")
        }
        assert entries == self._public_callables()

    def test_the_module_docstring_names_every_public_function(self) -> None:
        """Same for the thing ``help(esolangs)`` shows first."""
        doc = esolangs.__doc__ or ""
        missing = sorted(n for n in self._public_callables() if n not in doc)
        assert not missing, f"esolangs.__doc__ omits: {missing}"


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


class TestAWidthAwareGeneratorCanStillOverrun:
    """The docstring named LaserFuck; Streetcode is the worse of the two.

    Both take the width themselves rather than being reflowed afterwards,
    which reads as a guarantee and is not one -- a token wider than the
    width has to go somewhere.  These two are the measured witnesses.
    """

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

    def test_the_pair_is_still_width_aware(self) -> None:
        """The two this class measures must stay in the group it measures.

        It used to assert the group was *only* these two, which stopped
        being true the moment another generator learned to lay itself out
        -- and that is a good change failing a test, not a regression.  The
        claim worth keeping is narrower: if either of these drops out of
        the group, the overrun numbers above are measuring nothing.
        """
        aware = {
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["width_aware"]
        }
        assert {"LaserFuck", "Streetcode"} <= aware


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

        The split itself is not pinned.  It was ``{none: 38, wrap: 29,
        layout: 2}`` and one campaign of teaching generators to lay
        themselves out made it ``{none: 22, wrap: 35, layout: 12}`` -- so a
        pinned split tests how far that campaign has got, not the property
        this class is about.  What has to hold is that all three stay
        populated, since ``width_aware`` is ``False`` for two of them and
        that is what a reader ran into.
        """
        counts: dict[str, int] = {}
        for name in esolangs.list_languages():
            effect = str(esolangs.describe(name)["width_effect"])
            counts[effect] = counts.get(effect, 0) + 1
        assert set(counts) == {"none", "wrap", "layout"}
        assert min(counts.values()) > 1, counts
        assert sum(counts.values()) == len(esolangs.list_languages())


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


class TestFillingSomethingWithNoSlots:
    """ "0 inputs" is true and answers a question nobody asked."""

    def test_a_plain_program_says_it_is_not_a_template(self) -> None:
        """The mistake is "this is not a template", not a count of zero."""
        with pytest.raises(esolangs.TemplateError, match=re.escape("no run of '$'")):
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
        with pytest.raises(esolangs.TemplateError, match="2 inputs"):
            esolangs.instantiate("Minifuck", template, [1, 0, 1])


class TestEvaluateTakesAWidth:
    """Checking a wrapped program meant reimplementing the loop.

    A width is the one build option that can change whether the program
    still *works* -- a break inside a token computes a different table, or
    none -- so "does it survive the wrap" is the round trip most worth
    running.  ``evaluate`` and ``verify`` did not take one, and hand-rolling
    it also lost the divergence proof, which turns the four languages that
    answer 1 by not terminating from milliseconds into a full bound per
    1-row.
    """

    @pytest.mark.medium
    def test_every_language_survives_a_wrap(self) -> None:
        """All 60, because a wrapper that broke one would break it quietly.

        1.8s for the set at two inputs, which is the whole point of doing it
        here rather than leaving it to a caller who has to write the loop.
        """
        wrong = [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["boolean_generator"]
            and esolangs.evaluate(name, "0110", timeout=30, width=40) != "0110"
        ]
        assert not wrong

    @pytest.mark.parametrize(
        ("name", "effect"),
        # Clockwise used to stand for "none" and now stacks its tree to a
        # width, which is what pinning the effect against ``describe`` is
        # for: it failed here rather than turning this into a test of
        # "wrap" twice.  CV(N)(C) rejects newlines outright, so it cannot
        # migrate the same way.
        [("brainfuck", "wrap"), ("LaserFuck", "layout"), ("CV(N)(C)", "none")],
    )
    def test_it_works_for_each_width_effect(self, name: str, effect: str) -> None:
        """The three things a width can do, one language each.

        Pinned against ``describe`` rather than named in prose, so a
        language that changes effect fails here instead of quietly making
        this a test of one behaviour three times.
        """
        assert esolangs.describe(name)["width_effect"] == effect
        assert esolangs.evaluate(name, "0110", timeout=30, width=25) == "0110"

    def test_a_template_language_gets_the_width_too(self) -> None:
        """``evaluate`` applies the width once, and the rows still answer.

        A template wrapped to a width fills to a program with the same
        breaks (each run is its setter's width), and a caller writing the
        loop by hand can still wrap after filling; either way the width
        must not be applied twice.
        """
        assert esolangs.describe("Minifuck")["parameterized"] is True
        assert esolangs.evaluate("Minifuck", "0110", timeout=30, width=40) == "0110"

    def test_the_width_actually_reaches_the_program(self) -> None:
        """Otherwise this would pass with the argument thrown away."""
        wide = esolangs.generate("brainfuck", "10010110")
        narrow = esolangs.generate("brainfuck", "10010110", 30)
        assert "\n" not in wide  # the unwrapped default is one line
        assert "\n" in narrow
        assert max(len(line) for line in narrow.splitlines()) <= 30
        assert esolangs.evaluate("brainfuck", "10010110", width=30) == "10010110"

    def test_verify_takes_one_as_well(self) -> None:
        """It is ``evaluate`` with the comparison done, so it must pass it on."""
        assert esolangs.verify("brainfuck", "10010110", width=30)

    def test_no_width_is_unchanged(self) -> None:
        """The default has to stay exactly what it was."""
        assert esolangs.evaluate("brainfuck", "0110") == "0110"
        assert esolangs.verify("brainfuck", "0110")
