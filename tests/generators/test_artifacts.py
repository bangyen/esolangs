"""Artifact-backed source adapters preserve execution and persistence."""

import pickle
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from esolangs.runtime._artifacts import (
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
)
from esolangs.tagged import _Tagged, _Template
from tests.support.evaluation import _evaluate
from tests.support.pick import one, one_where
from tests.support.reference import REFERENCE

_EMBEDDING = one(parameterized=True, boolean_generator=True, answer_mode="output")
_PILOTS = [
    (language, "0110")
    for language in [
        REFERENCE,
        *_EMBEDDING,
        *one(source_kind="raster", boolean_generator=True, answer_mode="output"),
    ]
] + [
    (language, "01")
    for language in one_where(
        lambda info: LANGUAGES[info["name"]].compressed_source, boolean_generator=True
    )
]


@pytest.mark.medium
@pytest.mark.parametrize(("language", "table"), _PILOTS)
def test_artifact_persistence_executes_the_same_table(
    language: str, table: str, tmp_path: Path
) -> None:
    inputs = len(table).bit_length() - 1
    source = esolangs.generate(language, table)
    document = esolangs.dump_program(language, source)
    restored = esolangs.load_program(language, document)
    assert esolangs.dump_program(language, restored) == document
    for program in (source, restored, pickle.loads(pickle.dumps(source))):
        assert _evaluate(language, program, inputs=inputs) == table
    path = tmp_path / ("program" + LANGUAGES[language].source_suffix)
    esolangs.save_program(source, path)
    assert _evaluate(language, path, inputs=inputs) == table


@pytest.mark.medium
@pytest.mark.parametrize("language", [REFERENCE, *_EMBEDDING])
def test_text_adapter_converts_to_an_immutable_record(language: str) -> None:
    source = esolangs.generate(language, "0110")
    assert isinstance(source, _Tagged)
    artifact = source._artifact
    assert artifact.source == str(source)
    assert type(artifact.source) is str
    assert artifact.language == language
    with pytest.raises(FrozenInstanceError):
        artifact.language = "other"
    if isinstance(source, _Template):
        assert isinstance(artifact, TemplateArtifact)
        filled = artifact.bindings.fill(artifact.source, [0, 1])
        assert filled == source.fill([0, 1])
        assert esolangs.run(language, filled) == "1"
    else:
        assert isinstance(artifact, ProgramArtifact)


@pytest.mark.parametrize("bits", [[0], [0, 1, 0], [0, True], [0, 2]])
def test_template_record_refuses_invalid_bindings(bits: list[int]) -> None:
    template = TemplateArtifact(
        "$$", REFERENCE, TemplateBindings(setters=(("0", "1"),) * 2)
    )
    with pytest.raises((esolangs.TemplateError, esolangs.ArgumentError)):
        template.bindings.fill(template.source, bits)


@pytest.mark.parametrize(
    ("source", "setters"),
    [("$", (("0", "11"),)), ("$$", (("0", "1"),)), ("x", (("0", "1"),))],
)
def test_template_record_refuses_invalid_shape(source, setters) -> None:
    with pytest.raises(ValueError, match=r"width|belongs to no input|run"):
        TemplateArtifact(source, REFERENCE, TemplateBindings(setters=setters))


@pytest.mark.parametrize("language", _EMBEDDING)
def test_generated_and_restored_bindings_need_no_recovery(
    language, monkeypatch
) -> None:
    source = esolangs.generate(language, "0110")
    restored = esolangs.load_program(language, esolangs.dump_program(language, source))

    def refuse_recovery(*_args):
        raise AssertionError("lost explicit input bindings")

    monkeypatch.setattr(esolangs, "recover_setters", refuse_recovery)
    for template in (source, restored):
        with pytest.raises(esolangs.TemplateError):
            esolangs.run(language, template)
        with pytest.raises(esolangs.TemplateError):
            esolangs.instantiate(REFERENCE, template, [0, 1])
        filled = esolangs.instantiate(language, template, [0, 1])
        with pytest.raises(esolangs.ProgramError):
            esolangs.run(REFERENCE, filled)


def test_template_record_copies_bindings_and_retains_settings() -> None:
    settings = esolangs.DialectSettings()
    pairs = [["0", "1"]]
    template = TemplateArtifact(
        "$", REFERENCE, TemplateBindings(setters=pairs), settings=settings
    )
    pairs[0][1] = "changed"
    assert template.bindings.fill(template.source, [1]) == "1"
    assert template.language == REFERENCE
    assert template.settings is settings
