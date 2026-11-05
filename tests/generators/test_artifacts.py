"""Artifact-backed source adapters preserve execution and persistence."""

import pickle
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import esolangs
from esolangs import compat
from esolangs.artifacts import (
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
)
from esolangs.registry import LANGUAGES
from esolangs.tagged import _Tagged, _Template, source_adapter
from tests.support.evaluation import _evaluate
from tests.support.pick import languages, one, one_where
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
        lambda info: LANGUAGES[info["name"]].runtime.compressed_source,
        boolean_generator=True,
    )
]


@pytest.mark.medium
@pytest.mark.parametrize(("language", "table"), _PILOTS)
def test_artifact_persistence_executes_the_same_table(
    language: str, table: str, tmp_path: Path, monkeypatch
) -> None:
    import esolangs.portable as portable

    inputs = len(table).bit_length() - 1
    choices = esolangs.DialectSettings()
    scale = 2 if LANGUAGES[language].runtime.source_kind == "raster" else 1
    source = esolangs.generate_artifact(language, table, scale=scale, settings=choices)

    def refuse_adapter(*_args):
        raise AssertionError("explicit artifact converted to compatibility source")

    with monkeypatch.context() as patch:
        patch.setattr(compat, "source_adapter", refuse_adapter)
        patch.setattr(portable, "source_adapter", refuse_adapter)
        document = esolangs.dump_program(language, source)
        restored = esolangs.load_artifact(language, document)
        assert esolangs.dump_program(language, restored) == document
        assert type(source) is type(restored)
        assert source.settings == restored.settings == choices
        assert source.language == restored.language == language
        assert esolangs.Language(language).load_artifact(document) == restored
        if isinstance(restored, TemplateArtifact):
            assert restored.bindings == source.bindings
            for isolated, max_steps in ((False, None), (False, 10_000), (True, 10_000)):
                with pytest.raises(esolangs.TemplateError):
                    esolangs.run(
                        language, restored, isolated=isolated, max_steps=max_steps
                    )
                result = esolangs.run(
                    language,
                    restored.fill([0, 1]),
                    isolated=isolated,
                    max_steps=max_steps,
                )
                assert result.output == "1"
        if isinstance(restored.source, esolangs.Raster):
            assert restored.scale == source.scale == 2
        if isinstance(restored, ProgramArtifact) and language != REFERENCE:
            with pytest.raises(esolangs.ProgramError):
                esolangs.run(REFERENCE, restored)
        for program in (source, restored, pickle.loads(pickle.dumps(source))):
            assert _evaluate(language, program, inputs=inputs) == table
    path = tmp_path / ("program" + LANGUAGES[language].source_suffix)
    esolangs.save_program(source, path)
    assert _evaluate(language, path, inputs=inputs) == table


@pytest.mark.medium
@pytest.mark.parametrize("language", [REFERENCE, *_EMBEDDING])
def test_text_adapter_converts_to_an_immutable_record(language: str) -> None:
    source = compat.generate(language, "0110")
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
        assert compat.run(language, filled) == "1"
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
    source = compat.generate(language, "0110")
    restored = compat.load_program(language, esolangs.dump_program(language, source))

    def refuse_recovery(*_args):
        raise AssertionError("lost explicit input bindings")

    monkeypatch.setattr(esolangs, "recover_setters", refuse_recovery)
    for template in (source, restored):
        with pytest.raises(esolangs.TemplateError):
            compat.run(language, template)
        with pytest.raises(esolangs.TemplateError):
            compat.instantiate(REFERENCE, template, [0, 1])
        filled = compat.instantiate(language, template, [0, 1])
        with pytest.raises(esolangs.ProgramError):
            compat.run(REFERENCE, filled)

    with pytest.raises(esolangs.TemplateError, match="fill the template"):
        esolangs.Language(language).from_source(source)


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


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "table", "options"),
    [
        (language, table, options)
        for language, table in _PILOTS
        for options in ({}, {"width": 3}, {"balance": True})
    ]
    + [
        (language, "0110", {"balance": True, "scale": 2})
        for language in languages(source_kind="raster", boolean_generator=True)
    ],
)
def test_generation_adapts_only_the_final_record(language, table, options, monkeypatch):
    exported = []
    adapt = compat.source_adapter

    def capture(artifact):
        exported.append(artifact)
        return adapt(artifact)

    monkeypatch.setattr(compat, "source_adapter", capture)
    source = compat.generate(language, table, **options)
    assert len(exported) == 1
    artifact = exported[0]
    assert isinstance(artifact, (ProgramArtifact, TemplateArtifact))
    assert artifact.language == language
    if isinstance(source, esolangs.Raster):
        assert source.scale == artifact.scale == options.get("scale", 1)
    assert _evaluate(language, source, inputs=len(table).bit_length() - 1) == table


@pytest.mark.medium
@pytest.mark.parametrize("language", _EMBEDDING)
def test_template_record_reuses_validated_runs_and_retains_provenance(
    language, monkeypatch
):
    import esolangs.artifacts as artifacts
    import esolangs.generation.helpers as helpers

    choices = esolangs.DialectSettings()
    artifact = esolangs.generate_artifact(language, "0110", settings=choices)
    assert isinstance(artifact, TemplateArtifact)
    source = source_adapter(artifact)

    def refuse_rescan(*_args):
        raise AssertionError("rescanned a validated template")

    monkeypatch.setattr(helpers, "runs", refuse_rescan)
    monkeypatch.setattr(artifacts, "runs", refuse_rescan)
    restored = source._artifact
    for bits, answer in [([0, 0], "0"), ([0, 1], "1"), ([1, 0], "1"), ([1, 1], "0")]:
        filled = artifact.fill(bits)
        assert isinstance(filled, ProgramArtifact)
        assert filled.language == language
        assert filled.settings is choices
        assert compat.run(language, filled.source) == answer
        assert restored.fill(bits).source == filled.source == source.fill(bits)


@pytest.mark.medium
def test_explicit_source_survives_all_execution_routes_and_persistence(tmp_path):
    language = esolangs.Language(REFERENCE)
    source = "program.bf"
    artifact = language.from_source(source)
    with pytest.raises(esolangs.ProgramError, match="looks like a path"):
        language.run(source)
    restored = language.load_artifact(language.dump_program(artifact))
    path = tmp_path / "source.txt"
    esolangs.save_program(artifact, path)
    loaded = language.from_file(str(path))
    assert artifact == restored == loaded
    for program in (artifact, restored, loaded):
        for isolated, max_steps in ((False, None), (False, 100), (True, 100)):
            result = language.run_result(
                program, isolated=isolated, max_steps=max_steps
            )
            assert result.output == "\x00"
            assert result.input_position == 0
            assert result.completion is not None

    language = esolangs.Language(REFERENCE)
    with pytest.raises(esolangs.ArgumentError, match="settings"):
        language.from_file(tmp_path / "absent.txt", settings={})
    with pytest.raises(esolangs.ArgumentError, match="path"):
        language.from_file(1)
    with pytest.raises(esolangs.ProgramNotFoundError):
        language.from_file(tmp_path / "absent.txt")


def test_public_records_canonicalize_and_validate_metadata():
    artifact = ProgramArtifact("+.", REFERENCE.upper())
    assert artifact.language == REFERENCE
    assert compat.run(REFERENCE, artifact) == "\x01"
    with pytest.raises(esolangs.ArgumentError):
        ProgramArtifact("+.", REFERENCE, scale=1)
    with pytest.raises(esolangs.ArgumentError):
        ProgramArtifact("+.", REFERENCE, settings={})
    with pytest.raises(esolangs.TemplateError):
        TemplateBindings(char="")
    template = TemplateArtifact("", REFERENCE.upper(), TemplateBindings())
    with pytest.raises(esolangs.TemplateError):
        esolangs.run(REFERENCE, template)

    with pytest.raises(esolangs.ProgramError):
        ProgramArtifact(b"+.", REFERENCE)
