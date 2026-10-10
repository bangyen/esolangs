"""The plumbing between a truth table and the answer bit a program prints."""

from __future__ import annotations

import pathlib
from importlib.resources import files

import pytest

import esolangs
import esolangs.debugger as debugger_api
from tests.generator_support import evaluate_generated
from tests.pick import first, languages

ROOT = pathlib.Path(__file__).parents[1]


README = (ROOT / "README.md").read_text()


USAGE_DOC = ROOT / "docs" / "usage.md"


#: The bit vector ``docs/usage.md``'s stdin table is rendered for; it has to
#: match the generator's ``_SAMPLE_BITS`` or the table cannot be compared.
_SAMPLE_BITS = [1, 0, 1]

#: Two template languages, for a template's checks and a foreign one.
TEMPLATED, OTHER_TEMPLATED = languages(parameterized=True)[-2:]


@pytest.mark.filterwarnings("ignore::UserWarning")
class TestTheProseMatchesTheData:
    """Three documents named the shapes; one of the four names was wrong."""

    def test_the_reference_table_is_the_encoders_own_output(self) -> None:
        """The positive half, as data: every cell is what ``encode_inputs`` returns."""
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
            if shape == "char_stream" and alphabet == ("0", "1"):
                continue
            stdin = esolangs.encode_inputs(name, _SAMPLE_BITS)
            expected[name] = (f"`{shape}`", f"`{stdin!r}`")

        assert rows == expected


class TestATemplateKnowsWhoseItIs:
    """Filling one as the wrong language ran, and answered a different row."""

    def test_a_foreign_template_is_refused(self) -> None:
        """It substituted RAM0's setter into a Minifuck program and answered 0."""
        template = esolangs.generate(TEMPLATED, "0110")
        with pytest.raises(esolangs.TemplateError, match="came from generate"):
            esolangs.instantiate(OTHER_TEMPLATED, template, [0, 1])

    def test_the_name_is_resolved_before_it_is_compared(self) -> None:
        """A case variant is the same language, not a mismatch."""
        template = esolangs.generate(TEMPLATED.lower(), "0110")
        assert esolangs.instantiate(TEMPLATED.upper(), template, [0, 1])


class TestATemplateCarriesItsSetters:
    """The conventions live on the template object, not on every caller."""

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

    def test_unequal_widths_are_refused(self) -> None:
        from esolangs.tagged import _Template

        with pytest.raises(ValueError, match="differ in width"):
            _Template("$", TEMPLATED, setters=[("x", "xx")])

    def test_runs_that_do_not_fit_the_setters_are_refused(self) -> None:
        from esolangs.tagged import _Template

        with pytest.raises(ValueError, match="shorter than its setter width"):
            _Template("a$b$$", TEMPLATED, setters=[("aa", "bb"), ("c", "d")])
        with pytest.raises(ValueError, match="belongs to no input"):
            _Template("a$$b$", TEMPLATED, setters=[("aa", "bb")])
        with pytest.raises(ValueError, match="1 run"):
            _Template("a$$b", TEMPLATED, setters=[("aa", "bb"), ("c", "d")])

    def test_a_fill_with_the_wrong_number_of_bits_is_refused(self) -> None:
        from esolangs.tools.helpers import fill_runs

        with pytest.raises(ValueError, match="expected 2 bits"):
            fill_runs("$$", "$", (("a", "b"), ("c", "d")), [1])

    def test_marks_are_read_off_the_languages_own_char(self) -> None:
        """The regression: ``$`` is INTERCAL's mingle operator, not its slot."""
        from esolangs.tools.helpers import mark, mark_runs

        pairs = (("xx", "yy"), ("p", "q"))
        # ``$`` here is ordinary text, exactly as a mingle operator would be.
        assert mark_runs("a@@$@b", "@", pairs) == (
            "a" + mark(0) * 2 + "$" + mark(1) + "b"
        )

    def test_a_zero_width_setter_has_an_empty_run(self) -> None:
        """An input spelled as nothing on both branches fills to nothing."""
        from esolangs.tools.helpers import fill_runs, runs

        pairs = (("", ""), ("xx", "yy"), ("", ""))
        assert runs("a$$b", "$", pairs) == [(0, 0), (1, 3), (3, 3)]
        assert fill_runs("a$$b", "$", pairs, [1, 0, 1]) == "axxb"
        assert fill_runs("a$$b", "$", pairs, [0, 1, 0]) == "ayyb"

    def test_adjacent_inputs_need_no_separator(self) -> None:
        from esolangs.tagged import _Template

        template = _Template("a$$$b", TEMPLATED, setters=[("xx", "yy"), ("p", "q")])
        assert template.fill([1, 0]) == "ayypb"
        assert template.fill([0, 1]) == "axxqb"

    def test_the_template_is_the_shape_of_every_program(self) -> None:
        """Every run is as long as its setter, so filling moves no character."""
        from esolangs.registry import template_body

        for name in languages(parameterized=True):
            template = esolangs.generate(name, "0110")
            shape = len(template_body(esolangs.describe(name)["id"], template))
            for bits in ([0, 0], [0, 1], [1, 0], [1, 1]):
                assert len(esolangs.instantiate(name, template, bits)) == shape

    def test_a_plain_string_is_filled_by_recovering_its_setters(self) -> None:
        for name in languages(parameterized=True):
            template = esolangs.generate(name, "0110")
            assert esolangs.instantiate(name, str(template), [1, 0]) == (
                esolangs.instantiate(name, template, [1, 0])
            ), name
        # Text no input count makes a template is refused by name, by every
        # language that recovers its setters from the text.
        refused = []
        for name in languages(parameterized=True):
            with pytest.raises(esolangs.TemplateError) as exc:
                esolangs.instantiate(name, "abc$$$", [1, 0])
            if str(exc.value).startswith(f"not a {name} templ"):
                refused.append(name)
        assert refused

    def test_the_setters_survive_a_width_and_a_pickle(self) -> None:
        import pickle

        template = esolangs.generate(TEMPLATED, "0110", width=20)
        assert template.setters == esolangs.generate(TEMPLATED, "0110").setters
        copied = pickle.loads(pickle.dumps(template))
        assert copied.setters == template.setters
        assert copied.char == template.char


class TestAProgramKnowsWhoseItIs:
    """A generated program run under another language is refused at the door."""

    def test_a_foreign_program_is_refused_by_run(self) -> None:
        program = esolangs.generate("brainfuck", "0110")
        with pytest.raises(esolangs.ProgramError, match="generated for brainfuck"):
            esolangs.run(TEMPLATED, program)

    def test_a_foreign_program_is_refused_by_make_vm(self) -> None:
        program = esolangs.generate("brainfuck", "0110")
        with pytest.raises(esolangs.ProgramError, match="generated for brainfuck"):
            debugger_api.make_vm(TEMPLATED, program, stdin="")

    def test_a_filled_template_carries_its_language(self) -> None:
        template = esolangs.generate(TEMPLATED, "0110")
        program = esolangs.instantiate(TEMPLATED, template, [0, 1])
        assert getattr(program, "language", None) == TEMPLATED
        with pytest.raises(esolangs.ProgramError, match=f"generated for {TEMPLATED}"):
            esolangs.run("brainfuck", program)

    def test_the_name_is_resolved_before_it_is_compared(self) -> None:
        program = esolangs.generate("BRAINFUCK", "0110")
        assert esolangs.run(
            "brainfuck", program, stdin=esolangs.encode_inputs("brainfuck", [0, 1])
        )

    def test_a_plain_string_is_accepted_unchecked(self) -> None:
        program = str(esolangs.generate("brainfuck", "0110"))
        assert getattr(program, "language", None) is None
        assert esolangs.run(
            "brainfuck", program, stdin=esolangs.encode_inputs("brainfuck", [0, 1])
        )

    def test_a_width_keeps_the_tag(self) -> None:
        program = esolangs.generate("brainfuck", "0110", width=20)
        assert getattr(program, "language", None) == "brainfuck"


class TestExamplePathsWorkFromAnywhere:
    """The recipe this package advertises worked from one directory."""

    def test_they_are_package_relative(self) -> None:
        """Absolute paths froze the install location into ``describe()``."""
        for name in esolangs.list_languages():
            for example in esolangs.describe(name)["examples"]:  # type: ignore[union-attr]
                assert example.startswith("examples/"), (name, example)

    def test_the_advertised_recipe_runs_from_another_directory(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A chdir away it was ``cannot read examples/brainfuck.txt``."""
        example = files("esolangs") / esolangs.describe("brainfuck")["examples"][0]
        monkeypatch.chdir(tmp_path)
        assert esolangs.run("brainfuck", example, stdin="1\n0\n", timeout=20)


@pytest.mark.filterwarnings("ignore::UserWarning")
class TestWhatHappensWhenAProgramIsUnderfed:
    """``run`` promised an exception for every language.  Most give it."""

    TABLE = "10010110"  # n = 3

    def _underfed(self, name: str) -> tuple[str, str | None]:
        """Return ``(outcome, answer)`` for ``name`` fed one bit too few."""
        program = esolangs.generate(name, self.TABLE)
        short = esolangs.encode_inputs(name, [1, 0])
        try:
            output = esolangs.run(name, program, stdin=short, timeout=10)
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
            if facts["input_shape"] == "char_stream_cyclic":
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

    def test_the_trait_is_reported_by_describe(self) -> None:
        """A caller must be able to learn this without underfeeding one."""
        assert languages(eof_is_a_value=True)
        assert languages(eof_is_a_value=False)


class TestInstantiateCanCheckProvenance:
    """A tag cannot survive a file, but a table can be compared against."""

    def test_a_hand_written_template_is_refused_given_the_table(self) -> None:
        """`"hello $$"` filled to `'hello [<'` and ran to nothing."""
        with pytest.raises(esolangs.TemplateError, match="is not the template"):
            esolangs.instantiate(TEMPLATED, "hello $$", [1], truth_table="01")


class TestSnapshotSaysItIsOpaque:
    """Its positions are not a schema and cannot be."""

    def test_the_docstring_says_so(self) -> None:
        """A reader asked what the fields were; there are no fields."""
        from esolangs.vm import _StepMachine

        doc = _StepMachine.snapshot.__doc__
        assert doc is not None
        assert "Opaque" in doc


class TestTheApiNameListsCannotDriftAgain:
    """Three rounds running, a reader found a public name in neither list."""

    @staticmethod
    def _public_callables() -> set[str]:
        """The exported names that are functions a caller would call."""
        import inspect

        return {
            name
            for name in esolangs.__all__
            if inspect.isfunction(getattr(esolangs, name))
        }

    def test_the_api_reference_lists_every_public_function(self) -> None:
        """The reference has to introduce all of it -- as a list, not a sentence."""
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


class TestTheDebuggerMirrorsSnapshot:
    """Reaching through ``.vm`` is what the mirrors exist to avoid."""

    def test_it_matches_the_wrapped_machine(self) -> None:
        """And is the thing a caller most wants: a repeated state."""
        program = esolangs.generate("brainfuck", "0110")
        stdin = esolangs.encode_inputs("brainfuck", [0, 1], truth_table="0110")
        debugger = debugger_api.make_debugger("brainfuck", program, stdin=stdin)
        assert debugger.snapshot() == debugger.vm.snapshot()
        before = debugger.snapshot()
        debugger.step()
        assert debugger.snapshot() != before


class TestTheTwoWidthKeysCannotDrift:
    """``width_aware`` is exactly ``width_effect == "layout"``."""

    def test_all_three_effects_are_represented(self) -> None:
        """A guard over a field with one value in practice guards nothing."""
        counts: dict[str, int] = {}
        for name in esolangs.list_languages():
            effect = str(esolangs.describe(name)["width_effect"])
            counts[effect] = counts.get(effect, 0) + 1
        assert set(counts) == {"none", "wrap", "layout"}
        assert min(counts.values()) > 1, counts
        assert sum(counts.values()) == len(esolangs.list_languages())


class TestEvaluateTakesAWidth:
    """Checking a wrapped program meant reimplementing the loop."""

    @pytest.mark.parametrize("effect", ["wrap", "layout", "none"])
    def test_it_works_for_each_width_effect(self, effect: str) -> None:
        """Width effects remain explicit for text and raster generators."""
        name = first(boolean_generator=True, width_effect=effect)
        assert evaluate_generated(name, "0110", timeout=30, width=25) == "0110"

    def test_a_template_language_gets_the_width_too(self) -> None:
        """``evaluate`` applies the width once, and the rows still answer."""
        assert evaluate_generated(TEMPLATED, "0110", timeout=30, width=40) == "0110"

    def test_the_width_actually_reaches_the_program(self) -> None:
        """Otherwise this would pass with the argument thrown away."""
        wide = esolangs.generate("brainfuck", "10010110")
        narrow = esolangs.generate("brainfuck", "10010110", width=30)
        assert "\n" not in wide  # the unwrapped default is one line
        assert "\n" in narrow
        assert max(len(line) for line in narrow.splitlines()) <= 30
        assert evaluate_generated("brainfuck", "10010110", width=30) == "10010110"
