"""Portable source survives disk with its dialect and template conventions."""

import json

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs.runtime._evaluate import _evaluate
from esolangs.tagged import _Tagged
from tests.api.test_dialects import CASES
from tests.support.reference import REFERENCE


@pytest.mark.medium
@pytest.mark.parametrize("language", [name for name, _ in CASES])
def test_restored_isolated_execution(language) -> None:
    source = esolangs.generate(language, "01", settings=dict(CASES)[language])
    restored = esolangs.load_program(language, esolangs.dump_program(language, source))
    assert _evaluate(language, restored, inputs=1, isolated=True) == "01"


@pytest.mark.medium
@pytest.mark.parametrize("choices", [None, DialectSettings()])
def test_default_settings_distinction(choices) -> None:
    document = esolangs.dump_program("Brainfuck", _Tagged("+.", REFERENCE, choices))
    restored = esolangs.load_program(REFERENCE, document)
    assert restored.settings == choices
    assert esolangs.run("Brainfuck", restored) == "\x01"


@pytest.mark.parametrize(
    "document", ["{", "null", "[]", "{}", '{"format":1,"format":2}']
)
def test_invalid_json(document) -> None:
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Brainfuck", document)


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
    document = json.loads(esolangs.dump_program("Brainfuck", "+."))
    document[field] = value
    with pytest.raises(esolangs.ProgramError):
        esolangs.load_program("Brainfuck", json.dumps(document))


def test_document_argument_and_invalid_settings() -> None:
    with pytest.raises(esolangs.ArgumentError, match="JSON string"):
        esolangs.load_program("Brainfuck", b"{}")
    with pytest.raises(esolangs.ArgumentError):
        esolangs.dump_program("Brainfuck", "+.", settings={})


def test_template_kind_requires_parameterized_language() -> None:
    document = json.loads(esolangs.dump_program("Brainfuck", "+."))
    document.update(kind="template", char="$", setters=[])
    with pytest.raises(esolangs.ProgramError, match="template char does not match"):
        esolangs.load_program("Brainfuck", json.dumps(document))
