"""Portable source survives disk with its dialect and template conventions."""

import json
from pathlib import Path

import pytest

import esolangs
from esolangs import ProgramArtifact
from esolangs.registry import template_char
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
    with pytest.raises(esolangs.ProgramError, match="template char does not match"):
        esolangs.from_json("Brainfuck", json.dumps(document))


@pytest.mark.parametrize("language", [REFERENCE, *one(parameterized=True)])
def test_export_refuses_templates_the_importer_would_reject(language) -> None:
    declared = template_char(esolangs.describe(language).id)
    marker = "_" if declared == "@" else "@"
    bindings = esolangs.TemplateBindings(char=marker, setters=(("+", "-"),))
    template = esolangs.TemplateArtifact(marker, language, bindings)
    with pytest.raises(esolangs.ProgramError, match="template char does not match"):
        esolangs.to_json(language, template)


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
