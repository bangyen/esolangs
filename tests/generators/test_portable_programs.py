"""Portable source survives disk with its dialect and template conventions."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

import esolangs
from esolangs import ProgramArtifact
from tests.support.dialect_support import CASES
from tests.support.evaluation import _evaluate
from tests.support.pick import one
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


def test_portable_storage_preserves_compression_for_text_languages(
    tmp_path: Path,
) -> None:
    api = esolangs.Language(REFERENCE)
    compressed = esolangs.CompressedText.from_chunks(("++.",))
    data = compressed.to_gzip()
    path = tmp_path / "source"
    path.write_bytes(data)
    expected = api.from_source(compressed)
    for supplied in (compressed, expected, data, path):
        restored = api.from_json(api.to_json(supplied))
        assert restored == expected
        assert api.run(restored).output == "\x02"


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
