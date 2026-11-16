"""Portable source survives disk with its dialect and template conventions."""

import gzip
import io
import json
import pickle
import zlib
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

import esolangs
from esolangs import ProgramArtifact
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import InputSlot, TemplateLayout, layout_tokens
from esolangs.generation.wrap import TokenWrapper, wrap_chars
from esolangs.registry import LANGUAGES
from esolangs.registry._backend import TemplateSpec
from tests.support.dialect_support import CASES
from tests.support.evaluation import _evaluate
from tests.support.pick import one, one_where
from tests.support.reference import REFERENCE


@pytest.mark.medium
@pytest.mark.parametrize("language", [name for name, _ in CASES])
def test_restored_isolated_execution(language) -> None:
    choices = dict(CASES)[language]
    source = esolangs.generate(language, "01", settings=choices)
    restored = esolangs.from_json(language, esolangs.to_json(language, source))
    assert restored.settings == source.settings == choices
    assert _evaluate(language, restored, inputs=1, isolated=True) == "01"


@pytest.mark.medium
@pytest.mark.parametrize("choices", [None, esolangs.Language("brainfuck").settings()])
def test_default_settings_distinction(choices) -> None:
    document = esolangs.to_json(
        REFERENCE, ProgramArtifact("+.", REFERENCE, settings=choices)
    )
    restored = esolangs.from_json(REFERENCE, document)
    assert restored.settings == choices
    assert esolangs.run("Brainfuck", restored).output == "\x01"
    empty = ProgramArtifact(
        esolangs.CompressedText.from_chunks(("",)), REFERENCE, settings=choices
    )
    document = esolangs.to_json(REFERENCE, empty)
    restored = esolangs.from_json(REFERENCE, document)
    assert restored == empty
    assert esolangs.run(REFERENCE, restored).output == ""
    missing_limits = json.loads(document)
    del missing_limits["limits"]
    with pytest.raises(esolangs.ProgramError, match="missing fields"):
        esolangs.from_json(REFERENCE, json.dumps(missing_limits))
    damaged = json.loads(document)
    damaged["source"] = ""
    with pytest.raises(esolangs.ProgramError, match="no gzip member"):
        esolangs.from_json(REFERENCE, json.dumps(damaged))


@pytest.mark.parametrize(
    "document", ["{", "null", "[]", "{}", '{"format":1,"format":2}']
)
def test_invalid_json(document) -> None:
    with pytest.raises(esolangs.ProgramError):
        esolangs.from_json("Brainfuck", document)
    for duplicated in ('{"format":1,"format":1}', '{"settings":{"key":1,"key":2}}'):
        with pytest.raises(esolangs.ProgramError, match="duplicate field"):
            esolangs.from_json("Brainfuck", duplicated)


def test_portable_document_uses_the_backing_text() -> None:
    class Document(str):
        def startswith(self, *_args, **_kwargs):
            raise AssertionError("called the document wrapper")

    api = esolangs.Language(REFERENCE)
    program = api.from_source("+.")
    document = api.to_json(program)
    restored = api.from_json(Document(document))
    assert restored == program
    assert api.run(restored).output == "\x01"
    with pytest.raises(esolangs.ProgramError, match="Unexpected UTF-8 BOM"):
        api.from_json(Document("\ufeff" + document))


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_portable_record_refuses_nonstandard_json_constants(constant: str) -> None:
    document = json.loads(esolangs.to_json(REFERENCE, "+."))
    document["settings"] = float(constant)
    with pytest.raises(
        esolangs.ProgramError, match=f"invalid JSON constant {constant}"
    ):
        esolangs.from_json(REFERENCE, json.dumps(document))


def test_portable_gzip_rejects_raster_language_before_expansion(monkeypatch) -> None:
    source = esolangs.CompressedText.from_chunks(("+.",))
    document = json.loads(esolangs.to_json(REFERENCE, source))
    assert esolangs.from_json(REFERENCE, json.dumps(document)).source == source
    name = one(source_kind="raster")[0]
    document["language"] = name

    def unexpected_expansion(_self):
        pytest.fail("the raster loader expanded a gzip source")

    monkeypatch.setattr(esolangs.CompressedText, "chunks", unexpected_expansion)
    with pytest.raises(esolangs.ProgramError, match="requires raster source"):
        esolangs.from_json(name, json.dumps(document))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("format", "other"),
        ("version", 2),
        ("source", 1),
        ("kind", "other"),
        ("settings", []),
        ("settings", {"eof": False}),
        ("settings", {"tape_size": {"integer": "0x!"}}),
        ("settings", {"tape_size": {}}),
        ("settings", {"boundary": "wrap"}),
        ("extra", None),
    ],
)
def test_invalid_fields(field, value) -> None:
    document = json.loads(esolangs.to_json("Brainfuck", "+."))
    document[field] = value
    with pytest.raises(esolangs.ProgramError):
        esolangs.from_json("Brainfuck", json.dumps(document))


def test_document_argument_and_invalid_settings() -> None:
    class ReportedType:
        def __init__(self, reported):
            self.reported = reported

        @property
        def __class__(self):
            return self.reported

    with pytest.raises(esolangs.ArgumentError, match="JSON string"):
        esolangs.from_json("Brainfuck", b"{}")
    with pytest.raises(esolangs.ArgumentError):
        esolangs.to_json("Brainfuck", "+.", settings={})
    api = esolangs.Language(REFERENCE)
    with pytest.raises(esolangs.ArgumentError, match="JSON string"):
        api.from_json(ReportedType(str))
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        api.to_json("+.", settings=ReportedType(esolangs.DialectSettings))
    with pytest.raises(esolangs.ArgumentError, match="DialectSettings"):
        ProgramArtifact(
            "+.", REFERENCE, settings=ReportedType(esolangs.DialectSettings)
        )
    for kind in (str, esolangs.CompressedText, esolangs.Raster):
        with pytest.raises(esolangs.ProgramError, match="a program needs"):
            ProgramArtifact(ReportedType(kind), REFERENCE)
    with pytest.raises(esolangs.ArgumentError, match="requires a language"):
        ProgramArtifact("+.", ReportedType(str))
    with pytest.raises(esolangs.ProgramError, match="gzip source must be bytes"):
        esolangs.CompressedText(ReportedType(bytes))
    with pytest.raises(esolangs.ArgumentError, match="TextLimits"):
        esolangs.CompressedText.from_chunks(
            ("+.",), limits=ReportedType(esolangs.TextLimits)
        )
    with pytest.raises(esolangs.ArgumentError, match="chunks must be strings"):
        esolangs.CompressedText.from_chunks([ReportedType(str)])
    with pytest.raises(esolangs.ArgumentError, match="one character"):
        esolangs.CompressedText.repeated(ReportedType(str), 1)

    from tests.support.pick import first

    language = first(source_kind="raster", boolean_generator=True)
    source = esolangs.generate(
        language, "01", settings=esolangs.Language(language).settings()
    )
    document = json.loads(esolangs.to_json(language, source))
    document["settings"] = None
    with pytest.raises(esolangs.ProgramError, match="conflicting PNG"):
        esolangs.from_json(language, json.dumps(document))


def test_template_kind_requires_parameterized_language() -> None:
    document = json.loads(esolangs.to_json("Brainfuck", "+."))
    document.update(kind="template", char="$", setters=[], spans=[])
    with pytest.raises(esolangs.ProgramError, match="does not support input templates"):
        esolangs.from_json("Brainfuck", json.dumps(document))
    bindings = esolangs.TemplateBindings(char="@", setters=(("+", "-"),))
    explicit = esolangs.TemplateArtifact("@", REFERENCE, bindings)
    with pytest.raises(esolangs.ProgramError, match="does not support input templates"):
        esolangs.to_json(REFERENCE, explicit)


@pytest.mark.parametrize("language", one(parameterized=True))
def test_ordered_template_setters_round_trip(language: str, tmp_path: Path) -> None:
    api = esolangs.Language(language)
    template = api.generate("01")
    assert isinstance(template, esolangs.TemplateArtifact)
    document = api.to_json(template)
    setters = template.bindings.setters
    for supplied in (setters, [list(pair) for pair in setters], map(iter, setters)):
        bindings = replace(template.bindings, setters=supplied)
        assert bindings.setters == setters
        retained = replace(template, bindings=bindings)
        assert retained.bindings is bindings
        assert api.to_json(retained) == document

    class AlternateInputs(esolangs.TemplateBindings):
        @property
        def inputs(self) -> int:
            return super().inputs + 1

    alternate = AlternateInputs(char=template.bindings.char, setters=setters)
    converted = replace(template, bindings=alternate)
    assert type(converted.bindings) is esolangs.TemplateBindings
    assert api.to_json(converted) == document

    class InvertedFill(esolangs.TemplateArtifact):
        def fill(self, bits):
            return super().fill([1 - bit for bit in bits])

    customized = InvertedFill(
        template.source,
        template.language,
        template.bindings,
        settings=template.settings,
        spans=template.spans,
    )
    assert api.to_json(customized) == document
    restored = api.from_json(api.to_json(customized))
    legacy = replace(template)
    object.__setattr__(legacy, "bindings", alternate)
    path = tmp_path / "program"
    for bit in (0, 1):
        expected = template.fill([bit]).source
        for shape in (tuple, list):

            class AlternateSpans(shape):
                def __iter__(self):
                    yield (-1, -1)

            supplied_spans = AlternateSpans(template.spans)
            assert (
                alternate.fill(template.source, [bit], spans=supplied_spans) == expected
            )
        assert api.read_answer(api.run(customized.fill([bit])).output) == str(1 - bit)
        assert customized.evaluate([bit]).answer == str(bit)
        assert api.instantiate(customized, [bit]).source == expected
        for candidate in (template, converted, customized, restored, legacy):
            assert api.evaluate(candidate, [bit]).answer == str(bit)
            filled = api.instantiate(candidate, [bit], truth_table="01")
            assert filled.source == expected
            api.to_file(filled, path)
            assert path.read_bytes() == expected.encode("utf-8")
            assert api.read_answer(api.run(path).output) == str(bit)

    malformed = json.loads(document)
    malformed["setters"] = ["01"]
    with pytest.raises(esolangs.ProgramError, match="setters must be pairs of strings"):
        api.from_json(json.dumps(malformed))


@pytest.mark.parametrize("language", one(parameterized=True))
@pytest.mark.parametrize("sequence_type", [tuple, list])
@pytest.mark.parametrize("level", ["inputs", "pair"])
def test_portable_template_setters_follow_stored_order(
    language: str, sequence_type: type, level: str
) -> None:
    class Reversed(sequence_type):
        def __iter__(self):
            return iter(self[::-1])

    api = esolangs.Language(language)
    generated = api.generate("0100")
    assert isinstance(generated, esolangs.TemplateArtifact)
    first, second = generated.bindings.setters
    setters = (first, second[::-1])
    control = replace(generated, bindings=replace(generated.bindings, setters=setters))
    supplied = (
        Reversed(setters)
        if level == "inputs"
        else tuple(Reversed(pair) for pair in setters)
    )
    bindings = replace(generated.bindings, setters=supplied)
    artifact = replace(generated, bindings=bindings)
    document = api.to_json(artifact)
    assert document == api.to_json(control)
    restored = api.from_json(document)
    assert restored == control
    for row, answer in enumerate("1000"):
        bits = [row >> 1, row & 1]
        assert (
            api.evaluate(restored, bits).answer
            == api.evaluate(control, bits).answer
            == answer
        )


@pytest.mark.parametrize("language", one(parameterized=True))
def test_template_owner_cannot_be_reassigned_by_an_alias(language: str) -> None:
    owner = esolangs.Language(language)
    declaration = owner.catalog.languages[language]
    renamed = replace(declaration, name="Scoped Template", id="", aliases=(language,))
    api = esolangs.Catalog([renamed]).bind(language)
    original = owner.generate("01", settings=owner.settings())
    native = api.generate("01", settings=api.settings())
    assert isinstance(original, esolangs.TemplateArtifact)
    assert isinstance(native, esolangs.TemplateArtifact)
    assert api.name == renamed.name
    assert api.instantiate(native, [1]) == native.fill([1])
    assert api.evaluate(native, [1]).answer == "1"
    assert owner.evaluate(original, [1]).answer == "1"
    with pytest.raises(esolangs.TemplateError, match="template belongs to"):
        api.instantiate(original, [1])
    with pytest.raises(esolangs.ProgramError, match="generated for"):
        original.evaluate([1], catalog=api.catalog)
    with pytest.raises(esolangs.ProgramError, match="program language must be"):
        api.from_json(owner.to_json(original))


@pytest.mark.parametrize("language", one(parameterized=True))
def test_explicit_template_marker_round_trips_in_its_catalog(language: str) -> None:
    declaration = esolangs.Language(language).catalog.languages[language]
    alias = "Private Alias"
    api = esolangs.Catalog([replace(declaration, aliases=(alias,))]).bind(alias)
    template = api.generate("01", settings=api.settings())
    assert isinstance(template, esolangs.TemplateArtifact)
    legacy = api.to_json(template)
    assert "generation_width" not in json.loads(legacy)
    assert api.to_json(api.from_json(legacy)) == legacy

    marker = "💡"
    assert marker not in template.source
    explicit = replace(
        template,
        source=template.source.replace(template.bindings.char, marker),
        bindings=esolangs.TemplateBindings(
            char=marker, setters=template.bindings.setters
        ),
    )
    document = api.to_json(explicit)
    restored = esolangs.from_json(alias, document, catalog=api.catalog)
    assert restored == explicit
    assert esolangs.to_json(alias, restored, catalog=api.catalog) == document
    saved = json.loads(document)
    saved["language"] = f" {api.name.swapcase()} "
    restored = api.from_json(json.dumps(saved))
    assert restored == explicit
    assert api.to_json(restored) == document
    for bit in (0, 1):
        assert api.evaluate(restored, [bit]).answer == str(bit)
    for wrong_owner in (alias, None, 1):
        saved["language"] = wrong_owner
        with pytest.raises(esolangs.ProgramError, match="program language must be"):
            api.from_json(json.dumps(saved))

    # Supplying settings rebuilds the artifact at the source boundary.
    width = 10**4301
    sized = replace(explicit, settings=None, generation_width=width)
    restored = api.from_json(api.to_json(sized, settings=explicit.settings))
    assert restored == replace(explicit, generation_width=width)
    for raw_width in (None, True, 0, -1, 8.0, "8"):
        damaged = json.loads(document)
        damaged["generation_width"] = raw_width
        with pytest.raises(esolangs.ProgramError, match="generation_width must be"):
            api.from_json(json.dumps(damaged))
    damaged = json.loads(api.to_json(api.from_source("")))
    damaged["generation_width"] = 8
    with pytest.raises(esolangs.ProgramError, match="unexpected or missing fields"):
        api.from_json(json.dumps(damaged))


@pytest.mark.parametrize("language", one(parameterized=True))
def test_explicit_template_marker_still_requires_exact_spans(language: str) -> None:
    api = esolangs.Language(language)
    bindings = esolangs.TemplateBindings(char="@", setters=(("", ""), ("+", "-")))
    explicit = esolangs.TemplateArtifact(
        "@", api.name, bindings, spans=((0, 0), (0, 1))
    )
    encoded = api.to_json(explicit)
    assert api.from_json(encoded) == explicit
    value = json.loads(encoded)
    for corrupt in (
        {"char": "@@"},
        {"source": "@@"},
        {"spans": []},
        {"spans": [[0, 0], [True, 1]]},
    ):
        with pytest.raises(esolangs.ProgramError):
            api.from_json(json.dumps({**value, **corrupt}))


@pytest.mark.parametrize("language", one(parameterized=True))
def test_explicit_zero_input_template_can_be_filled_after_reload(language: str) -> None:
    api = esolangs.Language(language)
    generated = api.generate("00")
    assert isinstance(generated, esolangs.TemplateArtifact)
    filled = generated.fill([0])
    record = esolangs.TemplateArtifact(
        filled.source,
        language,
        esolangs.TemplateBindings(char=generated.bindings.char),
        settings=filled.settings,
    )
    restored = api.from_json(api.to_json(record))
    assert isinstance(restored, esolangs.TemplateArtifact)
    assert restored == record
    for bits in ([], ()):
        assert restored.bindings.fill(restored.source, bits) == filled.source
        assert restored.fill(bits) == api.instantiate(restored, bits) == filled
        assert (
            restored.evaluate(bits).answer == api.evaluate(restored, bits).answer == "0"
        )
    with pytest.raises(esolangs.ArgumentError, match="0 inputs"):
        api.instantiate(restored, [0])
    with pytest.raises(esolangs.ArgumentError, match="must not be empty"):
        generated.fill([])
    with pytest.raises(esolangs.TruthTableError):
        api.generate("0")
    with pytest.raises(esolangs.ArgumentError, match="must not be empty"):
        esolangs.encode_inputs(REFERENCE, [])


def test_portable_storage_preserves_compression_for_text_languages(
    tmp_path: Path,
) -> None:
    api = esolangs.Language(REFERENCE)
    raw = b"++.\r\n"
    output = io.BytesIO()
    with gzip.GzipFile("original.bf", "wb", fileobj=output, mtime=123) as archive:
        archive.write(raw)
    data = output.getvalue()
    compressed = esolangs.CompressedText(data)
    path = tmp_path / "source"
    path.write_bytes(data)
    expected = api.from_source(compressed)
    loaded = api.from_file(path)
    assert loaded == api.prepare(path).artifact == expected
    document = api.to_json(path)
    assert json.loads(document)["kind"] == "gzip"
    for supplied in (compressed, expected, data, loaded):
        assert api.to_json(supplied) == document
    restored = api.from_json(document)
    for record in (loaded, restored):
        assert record == expected
        assert api.run(record).output == "\x02"
        saved = tmp_path / "saved"
        api.to_file(record, saved, gzip=True)
        assert saved.read_bytes() == data

    assert api.from_file(path, normalize=True) == api.from_source("++.")
    path.write_bytes(raw)
    assert api.from_file(path) == api.from_source(raw.decode("utf-8"))

    owner = replace(LANGUAGES[REFERENCE], name=REFERENCE.upper())
    scoped = esolangs.Catalog([owner]).bind(owner.name)
    for source in (raw.decode("utf-8"), compressed):
        original = scoped.from_source(source, settings=scoped.settings())
        saved = scoped.to_json(original)
        assert json.loads(saved)["language"] == owner.name != api.name
        assert scoped.from_json(saved) == original
        canonical = api.from_json(saved)
        assert canonical == api.from_source(source, settings=api.settings())
        assert json.loads(api.to_json(canonical))["language"] == api.name
        assert api.prepare(canonical).run().output == "\x02"


def test_portable_generation_preserves_backend_laid_out_compression(
    tmp_path: Path,
) -> None:
    original = LANGUAGES[REFERENCE]
    limits = esolangs.TextLimits(plain_chars=3, generation_chars=3, gzip_bytes=100)
    compressed = esolangs.CompressedText.from_chunks((",.",), limits=limits)

    def emit(request: GenerationRequest) -> esolangs.CompressedText:
        return compressed.wrapped(request.width)

    backend = replace(original.backend, entrypoint=emit, layout_width=True, wrap=None)
    api = esolangs.Catalog([replace(original, backend=backend)]).bind(REFERENCE)
    record = api.generate("01", width=2)
    restored = api.from_json(api.to_json(record))
    expected = compressed.wrapped(2)
    assert str(expected) == ",.\n"
    assert restored == record
    assert restored.source == expected
    assert restored.input_arity == 1
    path = tmp_path / "source.gz"
    api.to_file(restored, path, gzip=True)
    assert path.read_bytes() == expected.to_gzip()
    for bit in (0, 1):
        assert api.evaluate(restored, [bit]).answer == str(bit)


def test_portable_generation_honors_a_compressed_balancer() -> None:
    original = LANGUAGES[REFERENCE]
    original_limits = esolangs.TextLimits(
        plain_chars=0, generation_chars=8, gzip_bytes=80
    )
    returned_limits = esolangs.TextLimits(
        plain_chars=3, generation_chars=4, gzip_bytes=100
    )
    compressed = esolangs.CompressedText.from_chunks((",.",), limits=original_limits)
    output = gzip.compress(b",.\n\n", mtime=1)

    class AlternateBalance(esolangs.CompressedText):
        def _inherit_limits(self, _original):
            return self

    returned = AlternateBalance(output, limits=returned_limits)

    def balance(request: BalanceRequest) -> esolangs.CompressedText:
        assert request.source == compressed
        return returned

    backend = replace(
        original.backend, entrypoint=lambda _: compressed, balance=balance
    )
    api = esolangs.Catalog([replace(original, backend=backend)]).bind(REFERENCE)
    record = api.generate("01", balance=True)
    restored = api.from_json(api.to_json(record))
    assert restored == record
    assert isinstance(restored.source, esolangs.CompressedText)
    assert restored.source.to_gzip() == output
    assert restored.source.limits == esolangs.TextLimits(
        plain_chars=0, generation_chars=4, gzip_bytes=80
    )
    with pytest.raises(esolangs.GeneratorCapError, match="raw text"):
        str(restored.source)
    for bit in (0, 1):
        assert api.evaluate(restored, [bit]).answer == str(bit)


def test_unchanged_compressed_balance_reuses_limited_source(monkeypatch) -> None:
    original = LANGUAGES[REFERENCE]
    limits = esolangs.TextLimits(plain_chars=0, generation_chars=2, gzip_bytes=25)
    source = esolangs.CompressedText.from_chunks((",.",), limits=limits)
    backend = replace(
        original.backend, entrypoint=lambda _: source, balance=lambda req: req.source
    )
    api = esolangs.Catalog([replace(original, backend=backend)]).bind(REFERENCE)

    def unexpected_decode(_self):
        pytest.fail("an unchanged gzip source was revalidated")

    with monkeypatch.context() as patch:
        patch.setattr(esolangs.CompressedText, "chunks", unexpected_decode)
        balanced = api.generate("01", balance=True)
    assert balanced.source is source
    for bit in (0, 1):
        assert api.evaluate(balanced, [bit]).answer == str(bit)


@pytest.mark.parametrize("balance", [False, True])
def test_compressed_reflow_uses_declared_text_hooks(*, balance: bool) -> None:
    original = LANGUAGES[REFERENCE]
    limits = esolangs.TextLimits(plain_chars=0, generation_chars=20, gzip_bytes=100)
    compressed = esolangs.CompressedText.from_chunks((",.",), limits=limits)

    class AlternateChunks(esolangs.CompressedText):
        def chunks(self):
            yield "-."

    def reflow(text: str, width: int | None = None) -> str:
        assert text == ",."
        return text + (" balance" if width is None else " width")

    backend = replace(
        original.backend,
        wrap=None if balance else reflow,
        wrap_balance=reflow if balance else None,
    )
    sources = []
    for source in (
        ",.",
        compressed,
        AlternateChunks(compressed.to_gzip(), limits=limits),
    ):
        local = replace(
            original,
            backend=replace(backend, entrypoint=lambda _, source=source: source),
        )
        api = esolangs.Catalog([local]).bind(REFERENCE)
        record = api.generate("01", width=None if balance else 1, balance=balance)
        restored = api.from_json(api.to_json(record))
        assert restored == record
        for bit in (0, 1):
            assert api.evaluate(restored, [bit]).answer == str(bit)
        sources.append(restored.source)
    plain, packed, alternate = sources
    assert alternate == packed
    assert isinstance(packed, esolangs.CompressedText)
    assert (
        "".join(packed.chunks()) == plain == (",. balance" if balance else ",. width")
    )
    assert packed.limits == limits


@pytest.mark.parametrize("may_reflow", [False, True])
def test_compressed_reflow_respects_the_multiline_policy(*, may_reflow: bool) -> None:
    original = LANGUAGES[REFERENCE]
    raw = "," + "x" * 12 + "\n."
    limits = esolangs.TextLimits(
        plain_chars=0, generation_chars=len(raw), gzip_bytes=100
    )
    source = esolangs.CompressedText(
        gzip.compress(raw.encode(), mtime=1), limits=limits
    )

    def reflow(text: str, _width: int) -> str:
        assert may_reflow
        return text.replace("x", "").replace("\n", "")

    backend = replace(
        original.backend,
        entrypoint=lambda _: source,
        wrap=reflow,
        wrap_multiline=may_reflow,
    )
    api = esolangs.Catalog([replace(original, backend=backend)]).bind(REFERENCE)
    for options in ({"width": 1}, {"balance": True}):
        record = api.generate("01", **options)
        if not may_reflow:
            assert record.source is source
        restored = api.from_json(api.to_json(record))
        assert isinstance(restored.source, esolangs.CompressedText)
        assert "".join(restored.source.chunks()) == (",." if may_reflow else raw)
        assert restored.source.limits == limits
        for bit in (0, 1):
            assert api.evaluate(restored, [bit]).answer == str(bit)


@pytest.mark.parametrize("balance", [False, True])
@pytest.mark.parametrize("cap", ["work", "gzip"])
def test_compressed_reflow_enforces_original_generation_limits(
    cap: str, *, balance: bool
) -> None:
    original = LANGUAGES[REFERENCE]
    limits = esolangs.TextLimits(
        plain_chars=0,
        generation_chars=2 if cap == "work" else 100,
        gzip_bytes=100 if cap == "work" else len(gzip.compress(b",.", mtime=0)),
    )
    source = esolangs.CompressedText.from_chunks((",.",), limits=limits)
    expanded = ",.ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    returned = esolangs.CompressedText.from_chunks((expanded,))
    backend = replace(
        original.backend,
        entrypoint=lambda _: source,
        wrap=lambda _text, _width: expanded,
        balance=(lambda _: returned) if balance else None,
    )
    api = esolangs.Catalog([replace(original, backend=backend)]).bind(REFERENCE)
    match = "work cap" if cap == "work" else "file cap"
    with pytest.raises(esolangs.GeneratorCapError, match=match):
        api.generate("01", width=None if balance else 1, balance=balance)


@pytest.mark.parametrize(
    "language",
    one_where(
        lambda info: not LANGUAGES[info.name].runtime.file_newline,
        boolean_generator=True,
        width_effect="none",
    ),
)
def test_portable_compression_leaves_newline_tokens_unchanged(language: str) -> None:
    original = LANGUAGES[language]
    backend = original.backend
    assert backend is not None

    def emit(request: GenerationRequest) -> esolangs.CompressedText:
        source = backend.generate(request)
        assert isinstance(source, str)
        return esolangs.CompressedText.from_chunks((source,))

    declared = replace(original, backend=replace(backend, entrypoint=emit))
    api = esolangs.Catalog([declared]).bind(language)
    expected = api.generate("01")
    assert isinstance(expected.source, esolangs.CompressedText)
    for options in ({"width": 1}, {"balance": True}):
        restored = api.from_json(api.to_json(api.generate("01", **options)))
        assert restored == expected
        for bit in (0, 1):
            assert api.evaluate(restored, [bit]).answer == str(bit)


def _identity_layout(width: int | None = None, *, char: str = "$") -> TemplateLayout:
    return layout_tokens(
        ["+"] * 48 + [InputSlot(1), "."], width, char=char, separator=""
    )


def test_template_balancer_preserves_the_last_zero_width_slot() -> None:
    original = LANGUAGES[REFERENCE]
    layout = layout_tokens(["+" * 48 + ".", InputSlot(0)], separator="")

    def balance(request: BalanceRequest) -> TemplateLayout:
        assert isinstance(request.source, TemplateLayout)
        (line,) = request.source.lines()
        return line

    backend = replace(
        original.backend,
        entrypoint=lambda _: layout,
        template=TemplateSpec(pair=("", "")),
        balance=balance,
    )
    api = esolangs.Catalog([replace(original, backend=backend)]).bind(REFERENCE)
    record = api.generate("00", balance=True)
    assert record == api.generate("00")
    restored = api.from_json(api.to_json(record))
    assert restored == record
    assert restored.spans == ((49, 49),)
    for bit in (0, 1):
        assert api.evaluate(restored, [bit]).answer == "0"


def test_checked_portable_instantiation_accepts_balanced_eof_slot() -> None:
    original = LANGUAGES[REFERENCE]
    slot = InputSlot(0)
    plain = layout_tokens(["+" * 48 + ".", slot], separator="")
    balanced = layout_tokens(["+" * 24 + "\n" + "+" * 24 + ".", slot], separator="")
    requests = []
    extracted = []

    def emit(request: GenerationRequest) -> TemplateLayout:
        assert request not in requests
        requests.append(request)
        return plain

    def setters(text: str, inputs: int):
        key = text, inputs
        assert key not in extracted
        extracted.append(key)
        return (("", ""),) * inputs

    backend = replace(
        original.backend,
        entrypoint=emit,
        template=TemplateSpec(setters=setters),
        balance=lambda _: balanced,
    )
    api = esolangs.Catalog([replace(original, backend=backend)]).bind(REFERENCE)
    record = api.generate("00", balance=True)
    restored = api.from_json(api.to_json(record))
    assert isinstance(restored, esolangs.TemplateArtifact)
    assert restored == record
    assert restored.spans == ((50, 50),)
    requests.clear()
    extracted.clear()
    default = api.generate("00")
    requests.clear()
    extracted.clear()
    assert api.run(api.instantiate(default, [1], truth_table="00")).output == "0"
    assert [request.width for request in requests] == [None]
    assert extracted == [(plain.source, 1)]
    requests.clear()
    extracted.clear()
    with pytest.raises(esolangs.ProgramError, match="requires a slot-aware wrapper"):
        api.generate("00", width=1)
    for bit in (0, 1):
        assert api.evaluate(restored, [bit]).answer == "0"
        requests.clear()
        extracted.clear()
        filled = api.instantiate(restored, [bit], truth_table="00")
        assert [request.width for request in requests] == [None]
        assert extracted == [(plain.source, 1), (balanced.source, 1)]
        assert filled == restored.fill([bit])
        assert api.run(filled).output == "0"

    changed = replace(restored, source="+" + restored.source, spans=((51, 51),))
    assert api.run(changed.fill([0])).output == "1"
    requests.clear()
    extracted.clear()
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        api.instantiate(changed, [0], truth_table="00")


def test_checked_portable_instantiation_refuses_unbalanced_mismatch() -> None:
    original = LANGUAGES[REFERENCE]
    plain = layout_tokens(["+" * 48, InputSlot(1), "."], separator="")
    backend = replace(
        original.backend,
        entrypoint=lambda _: plain,
        template=TemplateSpec(pair=("x", "+")),
        layout_width=False,
        wrap=None,
        balance=None,
    )
    declaration = replace(original, backend=backend)
    api = esolangs.Catalog([declaration]).bind(REFERENCE)
    record = api.generate("01")
    restored = api.from_json(api.to_json(record))
    assert isinstance(restored, esolangs.TemplateArtifact)
    assert restored == record
    assert [
        api.run(api.instantiate(restored, [bit], truth_table="01")).output
        for bit in (0, 1)
    ] == ["0", "1"]

    changed = replace(restored, source="+" + restored.source, spans=((49, 50),))
    edited = api.from_json(api.to_json(changed))
    assert isinstance(edited, esolangs.TemplateArtifact)
    assert edited == changed
    assert [api.run(edited.fill([bit])).output for bit in (0, 1)] == ["1", "2"]
    with pytest.raises(esolangs.ProgramError, match="requires a slot-aware balancer"):
        api.generate("01", balance=True)
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        api.instantiate(edited, [1], truth_table="01")

    fault = esolangs.ProgramError("declared balancer failed")

    def fail(_request: BalanceRequest) -> TemplateLayout:
        raise fault

    declared = replace(declaration, backend=replace(backend, balance=fail))
    configured = esolangs.Catalog([declared]).bind(REFERENCE)
    with pytest.raises(esolangs.ProgramError) as refused:
        configured.instantiate(edited, [1], truth_table="01")
    assert refused.value is fault


@pytest.mark.parametrize("source", ["", "+\n"])
def test_template_layout_keeps_eof_slots_on_an_empty_line(source: str) -> None:
    layout = layout_tokens([source, InputSlot(0)], separator="")
    assert tuple(layout.lines()) == (
        *TemplateLayout(source, ()).lines(),
        TemplateLayout("", ((0, 0),)),
    )


def _check_width_provider_reuse() -> None:
    original = LANGUAGES[REFERENCE]
    requests = []
    extracted = []

    def emit(request: GenerationRequest) -> TemplateLayout:
        assert request not in requests
        requests.append(request)
        return _identity_layout(request.width)

    def setters(text: str, inputs: int):
        key = text, inputs
        assert key not in extracted
        extracted.append(key)
        return (("x", "+"),) * inputs

    for layout_width in (False, True):
        backend = replace(
            original.backend,
            entrypoint=emit,
            template=TemplateSpec(setters=setters),
            layout_width=layout_width,
            wrap=None if layout_width else wrap_chars,
        )
        api = esolangs.Catalog([replace(original, backend=backend)]).bind(REFERENCE)
        requests.clear()
        extracted.clear()
        generated = api.generate("01", width=8)
        restored = api.from_json(api.to_json(generated))
        assert isinstance(restored, esolangs.TemplateArtifact)
        assert "\n" in restored.source
        for bit, width in ((0, 8), (1, None)):
            requests.clear()
            extracted.clear()
            filled = api.instantiate(restored, [bit], width=width, truth_table="01")
            assert [request.width for request in requests] == (
                [None, 8] if layout_width else [None]
            )
            extra = (
                [(_identity_layout(1).source, 1)]
                if width is None and not layout_width
                else []
            )
            assert extracted == [
                (_identity_layout().source, 1),
                (restored.source, 1),
                *extra,
            ]
            assert api.run(filled).output == str(bit)

        altered = replace(
            restored, bindings=replace(restored.bindings, setters=(("+", "x"),))
        )
        assert api.run(altered.fill([0])).output == "1"
        requests.clear()
        extracted.clear()
        with pytest.raises(esolangs.TemplateError, match="not the template"):
            api.instantiate(altered, [0], width=8, truth_table="01")
        assert [request.width for request in requests] == [None]


def test_checked_portable_instantiation_uses_the_requested_native_width() -> None:
    _check_width_provider_reuse()
    original = LANGUAGES[REFERENCE]
    refuse_guesses = False
    rejected_width = esolangs.ArgumentError("width is outside this renderer's domain")

    def emit(request: GenerationRequest) -> TemplateLayout:
        if refuse_guesses and request.width == 1:
            raise rejected_width
        width = None if request.width is None else max(1, request.width - 1)
        return _identity_layout(width)

    backend = replace(
        original.backend,
        entrypoint=emit,
        template=TemplateSpec(pair=("x", "+")),
        layout_width=True,
        wrap=None,
        balance=lambda _: _identity_layout(9),
    )
    api = esolangs.Catalog([replace(original, backend=backend)]).bind(REFERENCE)
    record = api.generate("01", width=8)
    restored = api.from_json(api.to_json(record))
    assert isinstance(restored, esolangs.TemplateArtifact)
    assert restored == record
    assert restored.generation_width == 8
    assert max(map(len, restored.source.splitlines())) == 7
    pickled = pickle.loads(pickle.dumps(restored))
    assert pickled == restored
    legacy = api.from_json(api.to_json(replace(restored, generation_width=None)))
    assert legacy.generation_width is None
    for bit in (0, 1):
        for candidate in (record, restored, pickled):
            filled = api.instantiate(candidate, [bit], truth_table="01")
            assert filled == restored.fill([bit])
            assert api.run(filled).output == str(bit)
        filled = api.instantiate(legacy, [bit], width=8, truth_table="01")
        assert api.run(filled).output == str(bit)
    for unchecked_width in (legacy, replace(restored, generation_width=9)):
        with pytest.raises(esolangs.TemplateError, match="not the template"):
            api.instantiate(unchecked_width, [1], truth_table="01")

    refuse_guesses = True
    assert api.run(api.instantiate(restored, [1], truth_table="01")).output == "1"
    balanced = api.from_json(api.to_json(api.generate("01", balance=True)))
    for bit in (0, 1):
        filled = api.instantiate(balanced, [bit], truth_table="01")
        assert api.run(filled).output == str(bit)
    with pytest.raises(esolangs.ArgumentError) as caught:
        api.instantiate(balanced, [1], width=1, truth_table="01")
    assert caught.value is rejected_width

    retired_width = esolangs.ArgumentError("renderer no longer accepts width 8")

    def replacement_emit(request: GenerationRequest) -> TemplateLayout:
        if request.width == 8:
            raise retired_width
        return _identity_layout(request.width)

    replacement = esolangs.Catalog(
        [replace(original, backend=replace(backend, entrypoint=replacement_emit))]
    ).bind(REFERENCE)
    migrated = replacement.from_json(api.to_json(restored))
    for bit in (0, 1):
        filled = replacement.instantiate(migrated, [bit], truth_table="01")
        assert replacement.run(filled).output == str(bit)
    with pytest.raises(esolangs.ArgumentError) as caught:
        replacement.instantiate(migrated, [1], truth_table="01", width=8)
    assert caught.value is retired_width

    cap = esolangs.GeneratorCapError("renderer cannot lay out this width")

    def restricted_emit(request: GenerationRequest) -> TemplateLayout:
        if request.width in (1, 9):
            raise cap
        return _identity_layout(request.width)

    declaration = replace(
        original, backend=replace(backend, entrypoint=restricted_emit)
    )
    scoped = esolangs.Catalog([declaration]).bind(REFERENCE)
    saved = scoped.generate("01", width=8)
    portable = scoped.from_json(scoped.to_json(saved))
    assert isinstance(portable, esolangs.TemplateArtifact)
    assert portable == saved
    assert max(map(len, portable.source.splitlines())) == 8
    for bit in (0, 1):
        expanded = scoped.instantiate(portable, [bit], truth_table="01")
        assert expanded == saved.fill([bit])
        assert scoped.run(expanded).output == str(bit)
    with pytest.raises(esolangs.GeneratorCapError) as caught:
        scoped.instantiate(portable, [1], truth_table="01", width=1)
    assert caught.value is cap

    changed = replace(
        portable,
        source="+" + portable.source,
        spans=tuple((start + 1, end + 1) for start, end in portable.spans),
    )
    assert scoped.run(changed.fill([0])).output == "1"
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        scoped.instantiate(changed, [0], truth_table="01")

    def matcher(text, _plain, layout):
        return text == layout(9)

    custom = replace(
        declaration, backend=replace(declaration.backend, same_layout=matcher)
    )
    with pytest.raises(esolangs.GeneratorCapError) as caught:
        esolangs.Catalog([custom]).bind(REFERENCE).instantiate(
            changed, [0], truth_table="01"
        )
    assert caught.value is cap

    default_cap = esolangs.GeneratorCapError("renderer needs an explicit width")

    def explicit_only(request: GenerationRequest) -> TemplateLayout:
        if request.width is None:
            raise default_cap
        return restricted_emit(request)

    explicit = esolangs.Catalog(
        [replace(original, backend=replace(backend, entrypoint=explicit_only))]
    ).bind(REFERENCE)
    saved = explicit.generate("01", width=8)
    restored = explicit.from_json(explicit.to_json(saved))
    assert isinstance(restored, esolangs.TemplateArtifact)
    assert restored == saved
    for bit in (0, 1):
        for width in (None, 8):
            filled = explicit.instantiate(
                restored, [bit], truth_table="01", width=width
            )
            assert filled == restored.fill([bit])
            assert explicit.run(filled).output == str(bit)
    with pytest.raises(esolangs.GeneratorCapError) as caught:
        explicit.instantiate(restored, [1], truth_table="01", width=1)
    assert caught.value is cap
    with pytest.raises(esolangs.GeneratorCapError) as caught:
        explicit.instantiate(
            replace(restored, generation_width=None), [1], truth_table="01"
        )
    assert caught.value is default_cap
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        explicit.instantiate(changed, [1], truth_table="01", width=8)


@pytest.mark.parametrize("layout", [{"width": 8}, {"balance": True}])
def test_token_layout_keeps_the_custom_marker_in_portable_templates(layout) -> None:
    original = LANGUAGES[REFERENCE]
    marker = "💡"
    backend = replace(
        original.backend,
        entrypoint=lambda _: _identity_layout(char=marker),
        template=TemplateSpec(pair=("x", "+"), char=marker),
        wrap=TokenWrapper(r"[+.]"),
    )
    api = esolangs.Catalog([replace(original, backend=backend)]).bind(REFERENCE)
    record = api.generate("01", **layout)
    restored = api.from_json(api.to_json(record))
    assert isinstance(restored, esolangs.TemplateArtifact)
    assert restored == record
    assert "\n" in restored.source
    assert restored.bindings.char == marker
    for bit in (0, 1):
        filled = api.instantiate(restored, [bit], truth_table="01")
        assert api.run(filled).output == str(bit)

    relabeled = replace(
        restored,
        source=restored.source.replace(marker, "@"),
        bindings=replace(restored.bindings, char="@"),
    )
    assert api.instantiate(relabeled, [0], truth_table="01") == restored.fill([0])
    exchanged = replace(
        relabeled,
        source="@" + restored.source[1:],
        spans=((0, 1),),
    )
    assert api.run(exchanged.fill([0])).output == "/"
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        api.instantiate(exchanged, [0], truth_table="01")


def test_portable_compression_respects_raw_export_budget() -> None:
    api = esolangs.Language(REFERENCE)
    budget = esolangs.TextLimits(plain_chars=2, generation_chars=100, gzip_bytes=100)
    compressed = esolangs.CompressedText.from_chunks(("++.",), limits=budget)
    expected = api.from_source(compressed)
    for supplied in (compressed, expected):
        restored = api.from_json(api.to_json(supplied))
        assert restored == expected
        with pytest.raises(esolangs.GeneratorCapError, match="raw text"):
            str(restored.source)


def test_no_op_compressed_wrap_retains_the_archive_and_caps(tmp_path: Path) -> None:
    source = "+" * 1000 + "."
    size = len(source)
    # This encoding can fit the program in fewer bytes than the default gzip.
    encoder = zlib.compressobj(level=9, wbits=31, strategy=zlib.Z_RLE)
    data = encoder.compress(source.encode()) + encoder.flush()
    limits = esolangs.TextLimits(
        plain_chars=size, generation_chars=size, gzip_bytes=len(data)
    )

    class CompressedSubclass(esolangs.CompressedText):
        @property
        def __class__(self):
            return esolangs.Raster

    compressed = CompressedSubclass(data, limits=limits)
    wrapped = compressed.wrapped(size + 1)
    assert wrapped is compressed
    assert wrapped.limits is limits
    with pytest.raises(esolangs.GeneratorCapError, match="work cap"):
        compressed.wrapped(size)
    assert str(esolangs.CompressedText(data).wrapped(size)) == source + "\n"

    api = esolangs.Language(REFERENCE)
    restored = api.from_json(api.to_json(wrapped))
    assert restored == api.from_source(esolangs.CompressedText(data, limits=limits))
    assert api.run(restored).output == chr(1000 % 256)
    path = tmp_path / "program.gz"
    api.to_file(wrapped, path, gzip=True)
    assert path.read_bytes() == data
    assert api.run(api.from_file(path)).output == chr(1000 % 256)


def test_portable_compression_retains_only_the_declared_budget_fields() -> None:
    @dataclass(frozen=True, kw_only=True)
    class JobLimits(esolangs.TextLimits):
        job: str = "preview"

    api = esolangs.Language(REFERENCE)
    budgets = {"plain_chars": 0, "generation_chars": 2, "gzip_bytes": 100}
    base = esolangs.TextLimits(**budgets)
    supplied = JobLimits(**budgets)
    compressed = gzip.compress(b"..", mtime=1)
    for build in (
        lambda limits: esolangs.CompressedText(compressed, limits=limits),
        lambda limits: esolangs.CompressedText.from_chunks(("..",), limits=limits),
        lambda limits: esolangs.CompressedText.repeated(".", 2, limits=limits),
    ):
        plain = build(base)
        assert plain.limits is base
        source = build(supplied)
        assert type(source.limits) is esolangs.TextLimits
        assert source == plain
        assert source.to_gzip() == plain.to_gzip()
        artifact = api.from_source(source)
        document = api.to_json(artifact)
        assert json.loads(document)["limits"] == budgets
        restored = api.from_json(document)
        assert restored == artifact
        assert api.run(restored).output == "\x00\x00"

    source = esolangs.CompressedText(compressed, limits=base)
    legacy = esolangs.CompressedText(compressed, limits=base)
    # Older pickles can restore the original subclass without a constructor.
    object.__setattr__(legacy, "limits", supplied)
    document = api.to_json(legacy)
    assert json.loads(document)["limits"] == budgets
    assert api.from_json(document) == api.from_source(source)


def test_large_record_integers_stay_json_numbers() -> None:
    huge = 10**5000
    budgets = esolangs.TextLimits(
        plain_chars=huge, generation_chars=huge, gzip_bytes=huge
    )
    compressed = esolangs.CompressedText.from_chunks(("+.",), limits=budgets)
    original = ProgramArtifact(compressed, REFERENCE, input_arity=huge)
    document = esolangs.to_json(REFERENCE, original)
    wire = json.loads(document, parse_int=str)
    assert wire["input_arity"] == "1" + "0" * 5000
    assert wire["limits"] == dict.fromkeys(
        ("plain_chars", "generation_chars", "gzip_bytes"), wire["input_arity"]
    )
    assert esolangs.from_json(REFERENCE, document) == original


def test_source_records_freeze_the_underlying_text(tmp_path: Path) -> None:
    class Text(str):
        __hash__ = None

        def __str__(self):
            return "other"

        def encode(self, *_args, **_kwargs):
            return b"other"

    api = esolangs.Language(REFERENCE)
    original = ProgramArtifact(Text("+."), Text(api.name))
    expected = api.from_source("+.")
    assert type(original.source) is str
    assert type(original.language) is str
    assert original == expected
    assert hash(original) == hash(expected)
    assert api.run(original).output == "\x01"
    path = tmp_path / "source"
    api.to_file(original, path)
    assert api.from_file(path) == expected
    assert api.from_json(api.to_json(original)) == expected
