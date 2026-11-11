"""Immutable artifacts retain bindings, execution and persistence metadata."""

import pickle
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

import esolangs
from esolangs.artifacts import (
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
)
from esolangs.registry import LANGUAGES
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
    choices = esolangs.Language(language).settings()
    scale = 2 if LANGUAGES[language].runtime.source_kind == "raster" else 1
    source = esolangs.generate(language, table, scale=scale, settings=choices)

    def refuse_adapter(*_args):
        raise AssertionError("explicit artifact converted to compatibility source")

    with monkeypatch.context() as patch:
        patch.setattr(portable, "source_adapter", refuse_adapter, raising=False)
        patch.setattr(esolangs.Raster, "tagged", refuse_adapter, raising=False)
        document = esolangs.dump_program(language, source)
        restored = esolangs.load_program(language, document)
        assert esolangs.dump_program(language, restored) == document
        assert type(source) is type(restored)
        assert source.settings == restored.settings == choices
        assert source.language == restored.language == language
        assert esolangs.Language(language).load_program(document) == restored
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
    if isinstance(source, TemplateArtifact):
        document = tmp_path / "template.json"
        document.write_text(esolangs.dump_program(language, source))
        restored = esolangs.load_program(language, document.read_text())
        assert _evaluate(language, restored, inputs=inputs) == table
        for row, expected in enumerate(table):
            bits = [row >> shift & 1 for shift in reversed(range(inputs))]
            esolangs.save_program(esolangs.instantiate(language, restored, bits), path)
            result = esolangs.run(language, path, settings=source.settings)
            assert esolangs.read_answer(language, result.output) == expected
        return
    esolangs.save_program(source, path)
    assert _evaluate(language, path, inputs=inputs) == table


@pytest.mark.medium
@pytest.mark.parametrize("language", [REFERENCE, *_EMBEDDING])
def test_text_generation_returns_an_immutable_record(language: str) -> None:
    artifact = esolangs.generate(language, "0110")
    assert type(artifact.source) is str
    assert artifact.language == language
    with pytest.raises(FrozenInstanceError):
        artifact.language = "other"
    if isinstance(artifact, TemplateArtifact):
        filled = artifact.fill([0, 1])
        assert filled.source == artifact.bindings.fill(artifact.source, [0, 1])
        assert esolangs.run(language, filled).output == "1"
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

    monkeypatch.setattr(esolangs, "_recover_template", refuse_recovery, raising=False)
    for template in (source, restored):
        with pytest.raises(esolangs.TemplateError):
            esolangs.run(language, template)
        with pytest.raises(esolangs.TemplateError):
            esolangs.instantiate(REFERENCE, template, [0, 1])
        filled = esolangs.instantiate(language, template, [0, 1])
        with pytest.raises(esolangs.ProgramError):
            esolangs.run(REFERENCE, filled)

    with pytest.raises(esolangs.TemplateError, match="fill the template"):
        esolangs.Language(language).from_source(source)


def test_template_record_copies_bindings_and_retains_settings() -> None:
    settings = esolangs.Language("brainfuck").settings()
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
def test_generation_keeps_the_final_record(language, table, options, monkeypatch):
    def forbid_adapter(*_args):
        raise AssertionError("generation adapted an explicit record")

    monkeypatch.setattr(esolangs.Raster, "tagged", forbid_adapter, raising=False)
    artifact = esolangs.generate(language, table, **options)
    assert isinstance(artifact, (ProgramArtifact, TemplateArtifact))
    assert artifact.language == language
    if isinstance(artifact.source, esolangs.Raster):
        assert artifact.scale == options.get("scale", 1)
    assert _evaluate(language, artifact, inputs=len(table).bit_length() - 1) == table


@pytest.mark.medium
@pytest.mark.parametrize("language", _EMBEDDING)
def test_template_record_reuses_validated_runs_and_retains_provenance(
    language, monkeypatch
):
    import esolangs._bindings as bindings
    import esolangs.artifacts as artifacts

    choices = esolangs.Language(language).settings()
    artifact = esolangs.generate(language, "0110", settings=choices)
    assert isinstance(artifact, TemplateArtifact)
    restored = esolangs.load_program(
        language, esolangs.dump_program(language, artifact)
    )

    def refuse_rescan(*_args):
        raise AssertionError("rescanned a validated template")

    monkeypatch.setattr(bindings, "runs", refuse_rescan)
    monkeypatch.setattr(artifacts, "runs", refuse_rescan)
    for bits, answer in [([0, 0], "0"), ([0, 1], "1"), ([1, 0], "1"), ([1, 1], "0")]:
        filled = artifact.fill(bits)
        assert isinstance(filled, ProgramArtifact)
        assert filled.language == language
        assert filled.settings is choices
        assert esolangs.run(language, filled).output == answer
        assert restored.fill(bits) == filled


@pytest.mark.medium
def test_explicit_source_survives_all_execution_routes_and_persistence(tmp_path):
    language = esolangs.Language(REFERENCE)
    source = "program.bf"
    artifact = language.from_source(source)
    assert language.run(source) == language.run(artifact)
    restored = language.load_program(language.dump_program(artifact))
    path = tmp_path / "source.txt"
    esolangs.save_program(artifact, path)
    loaded = language.from_file(str(path))
    assert artifact == restored == loaded
    for program in (artifact, restored, loaded):
        for isolated, max_steps in ((False, None), (False, 100), (True, 100)):
            result = language.run(program, isolated=isolated, max_steps=max_steps)
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
    assert artifact.language == REFERENCE.upper()
    canonical = esolangs.Language(REFERENCE.upper()).from_source(artifact.source)
    assert canonical.language == REFERENCE
    assert esolangs.run(REFERENCE, artifact).output == "\x01"
    with pytest.raises(esolangs.ArgumentError):
        ProgramArtifact("+.", REFERENCE, scale=1)
    with pytest.raises(esolangs.ArgumentError):
        ProgramArtifact("+.", REFERENCE, settings={})
    with pytest.raises(esolangs.TemplateError):
        TemplateBindings(char="")
    template = TemplateArtifact("", REFERENCE.upper(), TemplateBindings())
    with pytest.raises(esolangs.TemplateError):
        esolangs.run(REFERENCE, template)
    with pytest.raises(esolangs.TemplateError, match="fill the template"):
        ProgramArtifact(template, REFERENCE)
    with pytest.raises(esolangs.TemplateError, match="fill the template"):
        esolangs.Language(REFERENCE).from_source(template)

    with pytest.raises(esolangs.ProgramError):
        ProgramArtifact(b"+.", REFERENCE)

    name = one(source_kind="raster", boolean_generator=True)[0]
    generated = esolangs.generate(name, "01")
    settings = esolangs.Language(name).settings()
    native = esolangs.Raster(generated.source.rows)
    retained = ProgramArtifact(native, name, settings, generated.scale)
    assert retained.settings is settings
    assert retained.scale == generated.scale
    assert esolangs.run(name, retained, stdin="1\n").output == "1"

    class Text(str):
        language = name
        settings = "invalid"

    declared = ProgramArtifact(Text("+."), REFERENCE)
    assert declared.settings is None
    assert esolangs.run(REFERENCE, declared).output == "\x01"
