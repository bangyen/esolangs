"""Immutable artifacts retain bindings, execution and persistence metadata."""

import io
import os
import pickle
import stat
from dataclasses import FrozenInstanceError, dataclass, replace
from pathlib import Path

import pytest

import esolangs
from esolangs.artifacts import (
    ProgramArtifact,
    TemplateArtifact,
    TemplateBindings,
)
from esolangs.generation.template import InputSlot, TemplateLayout, layout_tokens
from esolangs.generation.wrap import TokenWrapper, wrap_chars
from esolangs.registry import LANGUAGES, canonical_id
from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.runtime._files import _ANCHORED_STAGING
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
        lambda info: LANGUAGES[info.name].runtime.compressed_source,
        boolean_generator=True,
    )
]


@dataclass(frozen=True, slots=True)
class _TemplateWithLabel(esolangs.TemplateArtifact):
    label: str = "width control"


def _check_template_width_pickle(template: esolangs.TemplateArtifact) -> None:
    labeled = _TemplateWithLabel(
        template.source,
        template.language,
        template.bindings,
        settings=template.settings,
        spans=template.spans,
        generation_width=template.generation_width,
    )

    class PreWidth:
        def __reduce__(self):
            return (
                object.__new__,
                (_TemplateWithLabel,),
                [
                    labeled.source,
                    labeled.language,
                    labeled.bindings,
                    labeled.settings,
                    labeled.spans,
                    labeled.label,
                ],
            )

    restored = pickle.loads(pickle.dumps(labeled))
    assert restored == labeled
    assert restored.generation_width == labeled.generation_width
    legacy = pickle.loads(pickle.dumps(PreWidth()))
    assert legacy == replace(labeled, generation_width=None)
    assert legacy.label == labeled.label
    assert legacy.generation_width is None


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
        document = esolangs.to_json(language, source)
        restored = esolangs.from_json(language, document)
        assert esolangs.to_json(language, restored) == document
        assert type(source) is type(restored)
        assert source.settings == restored.settings == choices
        assert source.language == restored.language == language
        assert esolangs.Language(language).from_json(document) == restored
        if isinstance(restored, TemplateArtifact):
            _check_template_width_pickle(replace(restored, generation_width=8))
            assert restored.bindings == source.bindings
            for isolated, max_steps in ((False, None), (False, 10_000), (True, 10_000)):
                with pytest.raises(esolangs.TemplateError):
                    esolangs.run(
                        language,
                        restored,
                        isolated=isolated,
                        limits=esolangs.ExecutionLimits(max_steps=max_steps),
                    )
                result = esolangs.run(
                    language,
                    restored.fill([0, 1]),
                    isolated=isolated,
                    limits=esolangs.ExecutionLimits(max_steps=max_steps),
                )
                assert result.output == "1"
        if isinstance(restored.source, esolangs.Raster):
            assert restored.scale == source.scale == 2
        if isinstance(restored, ProgramArtifact) and language != REFERENCE:
            with pytest.raises(esolangs.ProgramError):
                esolangs.run(REFERENCE, restored)
        current = pickle.loads(pickle.dumps(source))
        assert current == source
        for program in (source, restored, current):
            assert _evaluate(language, program, inputs=inputs) == table
    path = tmp_path / ("program" + LANGUAGES[language].source_suffix)
    if isinstance(source, TemplateArtifact):
        document = tmp_path / "template.json"
        document.write_text(esolangs.to_json(language, source))
        restored = esolangs.from_json(language, document.read_text())
        assert _evaluate(language, restored, inputs=inputs) == table
        for row, expected in enumerate(table):
            bits = [row >> shift & 1 for shift in reversed(range(inputs))]
            esolangs.to_file(
                language, esolangs.instantiate(language, restored, bits), path
            )
            result = esolangs.run(language, path, settings=source.settings)
            assert esolangs.read_answer(language, result.output) == expected
        return
    esolangs.to_file(language, source, path)
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


def test_template_bindings_require_ordered_pairs() -> None:
    class ReportedString:
        @property
        def __class__(self):
            return str

    for setters in (
        {("0", "1")},
        {"01": ("1", "0")},
        "",
        b"",
        [frozenset({"0", "1"})],
        [{"0": "1", "1": "0"}],
        ["01"],
        [(ReportedString(), "1")],
    ):
        with pytest.raises(
            esolangs.TemplateError, match=r"^setters must be pairs of strings$"
        ):
            TemplateBindings(setters=setters)
    with pytest.raises(esolangs.TemplateError, match="char must be one character"):
        TemplateBindings(char=ReportedString())
    with pytest.raises(esolangs.TemplateError, match="template needs text source"):
        TemplateArtifact(ReportedString(), REFERENCE, TemplateBindings())

    class OrderedPair:
        @property
        def __class__(self):
            return tuple

        def __iter__(self):
            return iter(("0", "1"))

    bindings = TemplateBindings(setters=[OrderedPair()])
    assert bindings.fill("$", [1]) == "1"

    class Offset(int):
        def __int__(self):
            raise AssertionError("converted the offset subclass")

        def __repr__(self):
            raise AssertionError("formatted the offset subclass")

        def __lt__(self, other):
            raise AssertionError("compared the offset subclass")

        def __floordiv__(self, other):
            raise AssertionError("divided the offset subclass")

    class Source(str):
        pass

    source = Source("$x")

    def emit(_request):
        return TemplateLayout(source, ((Offset(0), Offset(1)),))

    def setters(template, inputs):
        if "\n" not in template:
            assert template is source
        return (("0", "1"),) * inputs

    declaration = LANGUAGES[_EMBEDDING[0]]
    backend = BooleanBackend(
        emit, template=TemplateSpec(setters=setters), wrap=wrap_chars
    )
    scoped = esolangs.Catalog([replace(declaration, backend=backend)]).bind(
        declaration.name
    )
    plain = scoped.generate("01")
    wrapped = scoped.generate("01", width=1)
    assert plain.source == "$x"
    assert wrapped.source == "$\nx"
    assert wrapped.spans == ((0, 1),)
    assert wrapped.fill([1]).source == "1\nx"

    def invalid_layout(_request):
        return TemplateLayout(source, ((Offset(-1), Offset(1)),))

    invalid = esolangs.Catalog(
        [replace(declaration, backend=replace(backend, entrypoint=invalid_layout))]
    ).bind(declaration.name)
    with pytest.raises(
        esolangs.TemplateError, match=r"invalid template span \(-1, 1\)"
    ):
        invalid.generate("01", width=1)

    spans = ((Offset(0), Offset(1)),)
    template = TemplateArtifact("$", REFERENCE, bindings, spans=spans)
    assert template.spans == ((0, 1),)
    assert all(type(offset) is int for offset in template.spans[0])
    assert template.fill([1]).source == bindings.fill("$", [1], spans=spans) == "1"
    for bad in (True, 0.0, -1, Offset(-1)):
        with pytest.raises(esolangs.TemplateError, match="invalid template span"):
            TemplateArtifact("$", REFERENCE, bindings, spans=((bad, 1),))
        with pytest.raises(esolangs.TemplateError, match="invalid template span"):
            bindings.fill("$", [1], spans=((bad, 1),))
    with pytest.raises(esolangs.TemplateError, match="spans must be pairs of offsets"):
        TemplateArtifact("$", REFERENCE, bindings, spans=(OrderedPair(),))

    failure = esolangs.ProgramError("could not acquire setters")

    class FailingPair(OrderedPair):
        def __iter__(self):
            raise failure

    with pytest.raises(esolangs.ProgramError) as caught:
        TemplateBindings(setters=[FailingPair()])
    assert caught.value is failure


@pytest.mark.parametrize("language", _EMBEDDING)
def test_generated_and_restored_bindings_need_no_recovery(
    language, monkeypatch
) -> None:
    source = esolangs.generate(language, "0110")
    restored = esolangs.from_json(language, esolangs.to_json(language, source))

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
    _check_wrapped_template_width()


def _check_wrapped_template_width() -> None:
    original = LANGUAGES[REFERENCE]

    def layout(width=None):
        return layout_tokens([*("+" * 48), InputSlot(1), "."], width, separator="")

    backend = replace(
        original.backend,
        layout_width=False,
        entrypoint=lambda _: layout(),
        template=TemplateSpec(pair=("x", "+")),
        wrap=TokenWrapper(r"\+{11}|[\s\S]"),
        balance=lambda _: layout(9),
    )
    api = esolangs.Catalog([replace(original, backend=backend)]).bind(REFERENCE)
    record = api.generate("01", width=3)
    assert isinstance(record, TemplateArtifact)
    restored = api.from_json(api.to_json(record))
    assert isinstance(restored, TemplateArtifact)
    assert restored == record
    assert restored.generation_width == 3
    assert max(map(len, restored.source.splitlines())) == 11
    legacy = api.from_json(api.to_json(replace(restored, generation_width=None)))
    wrong = replace(restored, generation_width=4)
    for bit in (0, 1):
        for candidate in (record, restored, pickle.loads(pickle.dumps(restored))):
            filled = api.instantiate(candidate, [bit], truth_table="01")
            assert filled == record.fill([bit])
            assert api.run(filled).output == str(bit)
        for candidate in (legacy, wrong):
            filled = api.instantiate(candidate, [bit], width=3, truth_table="01")
            assert api.run(filled).output == str(bit)
    for candidate in (legacy, wrong):
        with pytest.raises(esolangs.TemplateError, match="not the template"):
            api.instantiate(candidate, [1], truth_table="01")
    with pytest.raises(esolangs.TemplateError, match="not the template"):
        api.instantiate(restored, [1], width=4, truth_table="01")


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
    restored = esolangs.from_json(language, esolangs.to_json(language, artifact))

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
    with pytest.raises(esolangs.ProgramError, match=r"pass its \.source"):
        language.from_source(artifact)  # type: ignore[arg-type]
    assert language.run(source) == language.run(artifact)
    restored = language.from_json(language.to_json(artifact))
    path = tmp_path / "source.txt"
    language.to_file(artifact, path)
    loaded = language.from_file(str(path))
    assert artifact == restored == loaded
    for program in (artifact, restored, loaded):
        for isolated, max_steps in ((False, None), (False, 100), (True, 100)):
            result = language.run(
                program,
                isolated=isolated,
                limits=esolangs.ExecutionLimits(max_steps=max_steps),
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
    retained = ProgramArtifact(native, name, settings=settings, scale=generated.scale)
    assert retained.settings is settings
    assert retained.scale == generated.scale
    assert esolangs.run(name, retained, stdin="1\n").output == "1"

    class Text(str):
        language = name
        settings = "invalid"

    declared = ProgramArtifact(Text("+."), REFERENCE)
    assert declared.settings is None
    assert esolangs.run(REFERENCE, declared).output == "\x01"


@pytest.mark.parametrize(
    "language",
    [
        name
        for parameterized in (False, True)
        for name in one_where(
            lambda info: (
                " " in info.name and all(part.isalpha() for part in info.name.split())
            ),
            parameterized=parameterized,
            boolean_generator=True,
        )
    ],
)
def test_retained_settings_accept_lexical_owner_spelling(language: str) -> None:
    installed = esolangs.Language(language)
    declaration = installed.catalog.languages[language]
    slug = canonical_id(language)
    alias, foreign_symbols = "Scoped Artifact Selector", f"{slug}++"
    scoped = replace(declaration, aliases=(alias, foreign_symbols))
    api = esolangs.Catalog([scoped]).bind(alias)
    generated = api.generate("01")
    settings = api.settings()

    for spelling in (
        f" \t{api.name.swapcase()} ",
        slug,
        api.name.replace(" ", "\N{NON-BREAKING HYPHEN}"),
    ):
        untagged = replace(generated, language=spelling, settings=None)
        assert untagged.language == spelling
        retained = replace(untagged, settings=settings)
        assert retained.language == api.name
        assert retained.settings is settings
        restored = api.from_json(api.to_json(retained))
        assert restored == api.from_json(api.to_json(untagged, settings=settings))
        assert restored == retained
        assert [api.evaluate(restored, [bit]).answer for bit in (0, 1)] == ["0", "1"]

    for foreign in scoped.aliases:
        assert api.catalog.resolve(foreign) == api.name
        with pytest.raises(esolangs.ArgumentError, match="settings belong to"):
            replace(generated, language=foreign, settings=settings)


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX symlink traversal")
def test_stream_export_retains_relative_symlink_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    actual = tmp_path / "actual"
    child = actual / "child"
    child.mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(child, target_is_directory=True)
    monkeypatch.chdir(tmp_path)

    api = esolangs.Language(REFERENCE)
    api.to_file(io.BytesIO(b"+."), "link/../program")
    assert not (tmp_path / "program").exists()
    assert (actual / "program").read_bytes() == b"+."
    assert set(actual.iterdir()) == {child, actual / "program"}
    assert api.run(actual / "program").output == "\x01"
    assert api.from_file("link/../program").source == "+."

    alternate = tmp_path / "alternate"
    other_child = alternate / "child"
    other_child.mkdir(parents=True)
    referent = tmp_path / "referent"
    referent.write_bytes(b"++.")
    refusal = esolangs.ProgramError("source refused")

    class RedirectedSource:
        def __init__(self, *, refuse: bool) -> None:
            self.refuse = refuse

        def read(self) -> bytes:
            link.unlink()
            link.symlink_to(other_child, target_is_directory=True)
            if self.refuse:
                raise refusal
            return b"+."

    for spelling, original, other in (
        ("link/program", child, other_child),
        ("link/../program", actual, alternate),
    ):
        destination = original / "program"
        destination.unlink(missing_ok=True)
        destination.symlink_to(referent)
        decoy = other / "program"
        decoy.write_bytes(b"+++.")
        entries = set(original.iterdir())
        with pytest.raises(esolangs.ProgramError) as caught:
            api.to_file(RedirectedSource(refuse=True), spelling)
        assert caught.value is refusal
        assert set(original.iterdir()) == entries
        assert destination.is_symlink()
        link.unlink()
        link.symlink_to(child, target_is_directory=True)
        api.to_file(RedirectedSource(refuse=False), spelling)
        assert set(original.iterdir()) == entries
        assert not destination.is_symlink()
        assert api.run(destination).output == "\x01"
        assert decoy.read_bytes() == b"+++."
        assert referent.read_bytes() == b"++."
        link.unlink()
        link.symlink_to(child, target_is_directory=True)

    if _ANCHORED_STAGING:
        _check_stream_export_after_parent_rename(tmp_path, api)
        _check_materialized_export_after_parent_rename(tmp_path, api)


def _check_stream_export_after_parent_rename(
    tmp_path: Path, api: esolangs.Language
) -> None:
    parent = tmp_path / "original"
    destination = parent / "program"
    moved = tmp_path / "moved"
    saved = moved / destination.name
    parent.mkdir()
    destination.write_bytes(b"++.")
    destination.chmod(0o644)
    refusal = esolangs.ArgumentError("reader refused after rename")

    class RenamingSource:
        def __init__(self, *, refuse: bool) -> None:
            self.refuse = refuse

        def read(self) -> bytes:
            parent.rename(moved)
            parent.mkdir()
            destination.write_bytes(b"+++.")
            saved.chmod(0o600)
            if self.refuse:
                raise refusal
            return b"+."

    with pytest.raises(esolangs.ArgumentError) as caught:
        api.to_file(RenamingSource(refuse=True), destination)
    assert caught.value is refusal
    assert set(moved.iterdir()) == {saved}
    assert saved.read_bytes() == b"++."
    destination.unlink()
    parent.rmdir()
    moved.rename(parent)
    destination.chmod(0o644)

    api.to_file(RenamingSource(refuse=False), destination)
    assert set(moved.iterdir()) == {saved}
    assert stat.S_IMODE(saved.stat().st_mode) == 0o600
    assert api.run(saved).output == "\x01"
    assert destination.read_bytes() == b"+++."


def _check_materialized_export_after_parent_rename(
    tmp_path: Path, api: esolangs.Language
) -> None:
    declaration = LANGUAGES[REFERENCE]
    schema = esolangs.DialectSchema(
        REFERENCE, {"mode": ("hold", "move")}, {"mode": "hold"}
    )
    parent = tmp_path / "materialized"
    moved = tmp_path / "saved"
    destination = parent / "program"
    saved = moved / destination.name
    refusal = esolangs.ArgumentError("validator refused after rename")
    phase = None
    calls = []

    def validate(mode="hold"):
        calls.append(mode)
        if phase is not None:
            parent.rename(moved)
            parent.mkdir()
            destination.write_bytes(b"+++.")
            saved.chmod(0o600)
            if phase == "refuse":
                raise refusal

    runtime = replace(declaration.runtime, dialect=validate, dialect_schema=schema)
    scoped = esolangs.Catalog([replace(declaration, runtime=runtime)]).bind(REFERENCE)
    settings = scoped.settings(mode="move")
    compressed = esolangs.CompressedText.from_chunks(("+.",))
    parent.mkdir()
    for source in ("+.", b"+.", api.from_source("+."), compressed):
        for phase in ("refuse", "save"):
            calls.clear()
            destination.write_bytes(b"++.")
            destination.chmod(0o644)
            if phase == "refuse":
                with pytest.raises(esolangs.ArgumentError) as caught:
                    scoped.to_file(source, destination, settings=settings)
                assert caught.value is refusal
                assert saved.read_bytes() == b"++."
            else:
                scoped.to_file(source, destination, settings=settings)
                assert api.run(saved).output == "\x01"
            assert calls == ["move"]
            assert stat.S_IMODE(saved.stat().st_mode) == 0o600
            assert destination.read_bytes() == b"+++."
            assert list(moved.iterdir()) == [saved]
            destination.unlink()
            parent.rmdir()
            moved.rename(parent)
