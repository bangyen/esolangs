"""Portable source survives disk with its dialect and template conventions."""

import gzip
import io
import json
from dataclasses import dataclass, replace
from pathlib import Path

import pytest

import esolangs
from esolangs import ProgramArtifact
from esolangs.generation.requests import BalanceRequest, GenerationRequest
from esolangs.generation.template import InputSlot, TemplateLayout, layout_tokens
from esolangs.generation.wrap import TokenWrapper
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
    with pytest.raises(esolangs.ArgumentError, match="JSON string"):
        esolangs.from_json("Brainfuck", b"{}")
    with pytest.raises(esolangs.ArgumentError):
        esolangs.to_json("Brainfuck", "+.", settings={})

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
def test_ordered_template_setters_round_trip(language: str) -> None:
    api = esolangs.Language(language)
    template = api.generate("01")
    assert isinstance(template, esolangs.TemplateArtifact)
    document = api.to_json(template)
    setters = template.bindings.setters
    for supplied in (setters, [list(pair) for pair in setters], map(iter, setters)):
        bindings = replace(template.bindings, setters=supplied)
        assert bindings.setters == setters
        assert api.to_json(replace(template, bindings=bindings)) == document
    restored = api.from_json(document)
    for bit in (0, 1):
        assert api.evaluate(restored, [bit]).answer == str(bit)

    malformed = json.loads(document)
    malformed["setters"] = ["01"]
    with pytest.raises(esolangs.ProgramError, match="setters must be pairs of strings"):
        api.from_json(json.dumps(malformed))


@pytest.mark.parametrize("language", one(parameterized=True))
def test_explicit_template_marker_round_trips_in_its_catalog(language: str) -> None:
    declaration = esolangs.Language(language).catalog.languages[language]
    alias = "Private Alias"
    api = esolangs.Catalog([replace(declaration, aliases=(alias,))]).bind(alias)
    template = api.generate("01", settings=api.settings())
    assert isinstance(template, esolangs.TemplateArtifact)
    legacy = api.to_json(template)
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
    for bit in (0, 1):
        assert api.evaluate(restored, [bit]).answer == str(bit)


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
    returned = esolangs.CompressedText(output, limits=returned_limits)

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

    def reflow(text: str, width: int | None = None) -> str:
        assert text == ",."
        return text + (" balance" if width is None else " width")

    backend = replace(
        original.backend,
        wrap=None if balance else reflow,
        wrap_balance=reflow if balance else None,
    )
    sources = []
    for source in (",.", compressed):
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
    plain, packed = sources
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


@pytest.mark.parametrize("source", ["", "+\n"])
def test_template_layout_keeps_eof_slots_on_an_empty_line(source: str) -> None:
    layout = layout_tokens([source, InputSlot(0)], separator="")
    assert tuple(layout.lines()) == (
        *TemplateLayout(source, ()).lines(),
        TemplateLayout("", ((0, 0),)),
    )


def test_checked_portable_instantiation_uses_the_requested_native_width() -> None:
    original = LANGUAGES[REFERENCE]

    def emit(request: GenerationRequest) -> TemplateLayout:
        width = None if request.width is None else max(1, request.width - 1)
        return _identity_layout(width)

    backend = replace(
        original.backend,
        entrypoint=emit,
        template=TemplateSpec(pair=("x", "+")),
        layout_width=True,
        wrap=None,
    )
    api = esolangs.Catalog([replace(original, backend=backend)]).bind(REFERENCE)
    record = api.generate("01", width=8)
    restored = api.from_json(api.to_json(record))
    assert isinstance(restored, esolangs.TemplateArtifact)
    assert restored == record
    assert max(map(len, restored.source.splitlines())) == 7
    for bit in (0, 1):
        filled = api.instantiate(restored, [bit], width=8, truth_table="01")
        assert filled == restored.fill([bit])
        assert api.run(filled).output == str(bit)


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
