"""Shared listing and specification contracts."""

import re
from dataclasses import replace
from pathlib import Path

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.runtime._execution import interpreter_module
from tests.support.cli_support import call_main
from tests.support.pick import first
from tests.support.reference import REFERENCE


def test_catalog_aliases_use_the_same_normalization_as_lookup() -> None:
    original = LANGUAGES[REFERENCE]
    scoped = esolangs.Catalog([replace(original, aliases=("  scoped-bf  ",))])
    assert scoped.resolve("SCOPED-BF") == REFERENCE
    other = replace(original, name="other", id="other", aliases=("scoped-bf",))
    with pytest.raises(esolangs.ArgumentError, match="one owner"):
        scoped.with_language(other)
    for alias in (None, " "):
        with pytest.raises(esolangs.ArgumentError, match="nonblank strings"):
            esolangs.Catalog([replace(original, aliases=(alias,))])


def test_catalog_identifiers_cannot_be_shadowed_by_aliases() -> None:
    original = LANGUAGES[REFERENCE]
    owner = replace(original, name="Private owner", id="private_owner")
    other = replace(original, name="Another", id="another", aliases=("PRIVATE_OWNER",))
    scoped = esolangs.Catalog([owner])
    assert scoped.resolve("private_owner") == owner.name
    with pytest.raises(esolangs.ArgumentError, match="one owner"):
        scoped.with_language(other)


def test_catalog_freezes_declaration_spellings_before_indexing() -> None:
    class WrappedText(str):
        __hash__ = None

        def strip(self, _chars=None):
            raise AssertionError("declaration called the string wrapper")

    original = LANGUAGES[REFERENCE]
    record = replace(
        original,
        name=WrappedText("Private interpreter"),
        id=WrappedText("private_interpreter"),
        aliases=(WrappedText("PRIVATE-ALIAS"),),
    )
    for scoped in (
        esolangs.Catalog([record]),
        esolangs.Catalog([]).with_language(record),
    ):
        assert scoped.resolve("private_interpreter") == "Private interpreter"
        assert scoped.bind("private-alias").run("+.").output == "\x01"


def test_bad_declaration_name_is_a_public_argument_error() -> None:
    with pytest.raises(esolangs.ArgumentError, match="nonblank strings"):
        replace(LANGUAGES[REFERENCE], name=42, id="")


@pytest.mark.parametrize("identifier", ["", "private_interpreter"])
def test_catalog_rejects_names_that_cannot_form_a_utf8_url(identifier: str) -> None:
    with pytest.raises(esolangs.ArgumentError, match=r"language names.*UTF-8"):
        replace(LANGUAGES[REFERENCE], name="Private\ud800", id=identifier)


def test_unicode_catalog_name_round_trips_and_forms_a_wiki_url() -> None:
    record = replace(LANGUAGES[REFERENCE], name="Private \N{SNAKE}", id="")
    api = esolangs.Catalog([record]).bind(record.id)
    assert api.describe().wiki_url.endswith("/Private_%F0%9F%90%8D")
    program = api.generate("01")
    restored = api.from_json(api.to_json(program))
    assert restored == program
    assert [api.evaluate(restored, [bit]).answer for bit in (0, 1)] == ["0", "1"]


def test_boolean_text_arguments_use_string_storage() -> None:
    class WrappedText(str):
        __hash__ = None

        def __iter__(self):
            raise AssertionError("truth table subclass was iterated")

        def strip(self, _chars=None):
            raise AssertionError("string subclass was stripped")

    api = esolangs.Language(REFERENCE)
    bound = api.catalog.bind(WrappedText(REFERENCE))
    assert type(bound.name) is str
    table = WrappedText("01")
    assert bound.encode_inputs([1], truth_table=table) == "1"
    assert bound.read_answer(WrappedText("1\n")) == "1"
    for balance in (False, True):
        program = bound.generate(table, balance=balance)
        assert program == api.generate("01", balance=balance)
        for bit in (0, 1):
            assert bound.evaluate(program, [bit]).answer == str(bit)


@pytest.mark.parametrize("sequence_type", [list, tuple])
def test_boolean_rows_use_the_sequence_contents(sequence_type: type) -> None:
    class WrappedRow(sequence_type):
        def __iter__(self):
            return iter((1,))

        def __len__(self):
            return 1

    api = esolangs.Language(REFERENCE)
    row = WrappedRow([0])
    assert api.encode_inputs(row) == "0"
    assert api.evaluate(api.generate("01"), row).answer == "0"
    with pytest.raises(esolangs.ArgumentError, match="must not be empty"):
        api.encode_inputs(WrappedRow())


def test_boolean_adapters_use_stdin_contract_without_a_generator() -> None:
    original = LANGUAGES[REFERENCE]
    api = esolangs.Catalog([replace(original, backend=None)]).bind(REFERENCE)
    facts = api.describe()
    assert not facts.boolean_generator
    assert facts.reads_input
    assert (facts.input_shape, facts.input_encoding) == ("char_stream", ("0", "1"))
    with pytest.raises(esolangs.ArgumentError, match="no boolean generator"):
        api.generate("01")
    program = api.from_source(",.")
    assert api.encode_inputs([1]) == "1"
    assert api.evaluate(program, [1]).answer == "1"


def test_read_answer_uses_the_first_group_of_the_last_match() -> None:
    original = LANGUAGES[REFERENCE]
    contract = replace(original.contract, answer_pattern=r"([01])([ab])")
    scoped = esolangs.Catalog([replace(original, contract=contract)])
    assert scoped.bind(REFERENCE).read_answer("0a, 1b") == "1"


def test_read_answer_reports_a_malformed_catalog_pattern() -> None:
    original = LANGUAGES[REFERENCE]
    contract = replace(original.contract, answer_pattern="wat(")
    scoped = esolangs.Catalog([replace(original, contract=contract)])
    with pytest.raises(esolangs.ProgramError, match="invalid answer pattern"):
        scoped.bind(REFERENCE).read_answer("1")


def test_scoped_description_uses_the_declared_runtime() -> None:
    original = LANGUAGES[REFERENCE]
    local = replace(
        original,
        name="Scoped runtime",
        id="scoped_runtime",
        runtime=replace(original.runtime, category="custom"),
    )
    scoped = esolangs.Catalog([local]).bind(local.name)
    assert scoped.describe().state_model == "other"
    assert scoped.describe().spec == esolangs.describe(REFERENCE).spec
    assert scoped.run("+.").output == "\x01"


def test_foreign_artifact_errors_agree_across_transports(tmp_path: Path) -> None:
    owner = esolangs.Language(first(source_kind="raster"))
    original = owner.catalog.languages[owner.name]
    local = replace(original, name="Private scope", id="private_scope")
    scoped = esolangs.Catalog([local]).bind(local.name)
    program = scoped.generate("01", scale=2)
    path = tmp_path / "scoped.png"
    scoped.to_file(program, path)
    document = scoped.to_json(program)
    assert scoped.from_json(document) == program
    assert scoped.from_file(path).source == program.source
    for operation in (
        lambda: owner.run(program),
        lambda: owner.prepare(program),
        lambda: owner.make_vm(program),
        lambda: owner.make_debugger(program),
        lambda: owner.evaluate(program, [1]),
        lambda: owner.to_file(program, tmp_path / "copy.png"),
        lambda: owner.to_json(program),
        lambda: owner.run(path),
        lambda: owner.from_file(path),
        lambda: owner.from_json(document),
    ):
        with pytest.raises(esolangs.ProgramError):
            operation()
    with pytest.raises(esolangs.UnknownLanguageError):
        esolangs.run(scoped.name, program)


def test_template_with_an_unregistered_owner_raises_template_error() -> None:
    owner = esolangs.Language(first(parameterized=True))
    original = owner.catalog.languages[owner.name]
    local = replace(original, name="Private template", id="private_template")
    scoped = esolangs.Catalog([local]).bind(local.name)
    template = scoped.generate("01")
    assert scoped.instantiate(template, [1]) == template.fill([1])
    result = template.evaluate([1], catalog=scoped.catalog)
    assert result == scoped.evaluate(template, [1])
    assert result.answer == "1"
    with pytest.raises(esolangs.TemplateError, match="belongs to"):
        owner.instantiate(template, [1])


def test_program_artifact_evaluation_can_select_a_scoped_contract() -> None:
    original = LANGUAGES[REFERENCE]
    swapped = replace(original.contract, answer_values=("1", "0"))
    scoped = esolangs.Catalog([replace(original, contract=swapped)]).bind(REFERENCE)
    program = scoped.generate("01")
    assert program.evaluate([1]).answer == "1"
    result = program.evaluate([1], catalog=scoped.catalog)
    assert result == scoped.evaluate(program, [1])
    assert result.answer == "0"


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
            if esolangs.describe(name).answer_mode == "dump"
            and not esolangs.describe(name).answer_pattern
            and not esolangs.describe(name).answer_convention
        ]
        assert not silent, (
            f"dump languages that never say where the answer is: {silent}"
        )


class TestTheSpecIsReachable:
    """Shared public contract."""

    def test_every_language_has_one(self) -> None:
        """The claim the feature rests on: there is something to show."""
        for name in esolangs.list_languages():
            assert len(esolangs.describe(name).spec) > 200, name

    def test_no_spec_shows_maintainer_detail(self) -> None:
        """Implementation notes are comments beside the code they explain."""
        leaks = {
            name: _MAINTAINER.findall(esolangs.describe(name).spec)
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
        spec = esolangs.describe(REFERENCE).spec
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
            esolangs.describe(REFERENCE)

    def test_it_still_returns_the_text_normally(self) -> None:
        """The abort must not have eaten the ordinary path."""
        assert esolangs.describe(REFERENCE).spec.startswith("Interpreter for")
