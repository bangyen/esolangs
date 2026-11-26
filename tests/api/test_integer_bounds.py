"""Shared public contracts, independent of language ownership."""

import sys
from dataclasses import replace

import pytest

import esolangs
from esolangs.registry import LANGUAGES
from tests.support.pick import first
from tests.support.reference import REFERENCE


@pytest.mark.parametrize(
    "operation",
    [
        lambda huge: (
            esolangs.run(
                REFERENCE, "", limits=esolangs.ExecutionLimits(execution_timeout=huge)
            )
            .unwrap()
            .output
        ),
        lambda huge: esolangs.ExecutionLimits(max_memory=-huge),
        lambda huge: (
            esolangs.run(
                REFERENCE, "", limits=esolangs.ExecutionLimits(execution_timeout=-huge)
            )
            .unwrap()
            .output
        ),
        lambda huge: (
            esolangs.run(
                REFERENCE,
                "",
                isolated=True,
                limits=esolangs.ExecutionLimits(max_output=-huge),
            )
            .unwrap()
            .output
        ),
        lambda huge: esolangs.generate(REFERENCE, "01", width=-huge),
        lambda huge: esolangs.encode_inputs(REFERENCE, [huge]),
        lambda huge: esolangs.encode_inputs(REFERENCE, [True, huge]),
        lambda huge: esolangs.Raster((((0, 0, 0),),)).upscaled(huge),
        lambda huge: esolangs.ProgramArtifact(
            ",.", REFERENCE, input_arity=huge
        ).evaluate([1]),
        lambda huge: (
            esolangs.run(
                first(source_kind="raster"),
                esolangs.Raster((((0, 0, 0),),)),
                scale=-huge,
            )
            .unwrap()
            .output
        ),
        lambda huge: (
            esolangs.run(
                REFERENCE,
                "",
                limits=esolangs.ExecutionLimits(execution_timeout={"value": huge}),
            )
            .unwrap()
            .output
        ),
    ],
)
def test_oversized_integer_arguments_keep_public_errors(operation) -> None:
    with pytest.raises(esolangs.ArgumentError) as caught:
        operation(10**5000)
    assert len(str(caught.value)) < 400


def test_recursive_invalid_limit_keeps_the_typed_error() -> None:
    cap = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(sys.int_info.str_digits_check_threshold)
        huge = 10**5000
        recursive: list[object] = [huge]
        recursive.append(recursive)
        with pytest.raises(esolangs.ArgumentError, match="max_steps") as caught:
            esolangs.ExecutionLimits(max_steps=recursive)  # type: ignore[arg-type]
        assert str(caught.value).endswith(
            f"[<integer with {huge.bit_length()} bits>, [...]]"
        )
    finally:
        sys.set_int_max_str_digits(cap)


def test_validation_uses_backing_types_without_reading_class_properties() -> None:
    probes: list[type] = []

    class Disguise:
        def __init__(self, claimed: type) -> None:
            self.claimed = claimed

        @property
        def __class__(self) -> type:
            probes.append(self.claimed)
            return self.claimed

        def __repr__(self) -> str:
            raise ValueError("unavailable representation")

    language = esolangs.Language(REFERENCE)
    artifact = language.generate("01")
    debugger = language.make_debugger("+.")
    disguised_limits = Disguise(esolangs.ExecutionLimits)
    for name, invoke in (
        ("max_steps", lambda: esolangs.ExecutionLimits(max_steps=Disguise(int))),
        ("max_memory", lambda: esolangs.ExecutionLimits(max_memory=Disguise(int))),
        (
            "total_timeout",
            lambda: esolangs.ExecutionLimits(total_timeout=Disguise(float)),
        ),
        ("width", lambda: esolangs.generate(REFERENCE, "01", width=Disguise(int))),
        ("seed", lambda: esolangs.run(REFERENCE, "+.", seed=Disguise(int)).unwrap()),
        (
            "isolated",
            lambda: esolangs.run(REFERENCE, "+.", isolated=Disguise(bool)).unwrap(),
        ),
        ("bits", lambda: esolangs.encode_inputs(REFERENCE, [Disguise(int)])),
        ("bits", lambda: esolangs.encode_inputs(REFERENCE, Disguise(list))),
        (
            "catalog",
            lambda: esolangs.Language(REFERENCE, catalog=Disguise(esolangs.Catalog)),
        ),
        (
            "catalog entries",
            lambda: esolangs.Catalog([Disguise(esolangs.LanguageDeclaration)]),
        ),
        ("limits", lambda: language.run("+.", limits=disguised_limits).unwrap()),
        ("limits", lambda: artifact.evaluate([1], limits=disguised_limits)),
        ("limits", lambda: debugger.run(limits=disguised_limits)),
    ):
        with pytest.raises(esolangs.ArgumentError, match=name):
            invoke()
    assert not probes
    assert not debugger.halted


def test_large_artifact_and_dialect_metadata_repr() -> None:
    cap = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(sys.int_info.str_digits_check_threshold)
        huge = 10**5000
        literal = hex(huge)
        schema = esolangs.DialectSchema(REFERENCE, {"mode": (1, huge)}, {"mode": huge})
        assert repr(schema).count(literal) == 2

        limits = esolangs.TextLimits(
            plain_chars=huge, generation_chars=huge, gzip_bytes=huge
        )
        compressed = esolangs.CompressedText.repeated("+", 1, limits=limits)
        assert repr(compressed).count(literal) == 3

        language = first(source_kind="raster")
        raster = esolangs.Raster((((0, 0, 0),),))
        artifact = esolangs.ProgramArtifact(
            raster, language, scale=huge, input_arity=huge
        )
        assert repr(artifact) == (
            f"ProgramArtifact(source=Raster(1x1), language={language!r}, "
            f"settings=None, scale={literal}, input_arity={literal})"
        )
    finally:
        sys.set_int_max_str_digits(cap)


def test_large_catalog_metadata_and_backend_request_repr() -> None:
    original = LANGUAGES[REFERENCE]
    generate = original.backend.generate
    huge = 10**5000
    literal = hex(huge)
    cap = sys.get_int_max_str_digits()
    touched = []

    def emit(request):
        assert request.width == request.options.integer("mode") == huge
        touched.append(repr(request))
        return generate(replace(request, width=None))

    schema = esolangs.DialectSchema(REFERENCE, {"mode": (1, huge)}, {"mode": huge})
    runtime = replace(
        original.runtime, dialect=lambda mode=huge: mode, dialect_schema=schema
    )
    backend = replace(
        original.backend, entrypoint=emit, layout_width=True, max_inputs=huge
    )
    declaration = replace(original, runtime=runtime, backend=backend)
    bound = esolangs.Catalog([declaration]).bind(REFERENCE)
    try:
        sys.set_int_max_str_digits(sys.int_info.str_digits_check_threshold)
        info = bound.describe()
        assert f"generator_max_inputs={literal}" in repr(info)
        assert repr(info).count(literal) == 3
        assert f"max_inputs={literal}" in repr(declaration)
        artifact = bound.generate("01", width=huge)
        assert touched == [
            f"GenerationRequest(table='01', width={literal}, "
            f"options=Options(values=(('mode', {literal}),)))"
        ]
        generated = replace(artifact, settings=None)
        assert "".join(generated.evaluate([bit]).answer for bit in (0, 1)) == "01"
    finally:
        sys.set_int_max_str_digits(cap)


@pytest.mark.parametrize("isolated", [False, True])
def test_execution_caps_use_the_integer_backing_value(isolated):
    class Limit(int):
        def __le__(self, _other):
            return False

        def __lt__(self, _other):
            return False

        def __int__(self):
            raise AssertionError("integer backing value must be used")

    limits = esolangs.ExecutionLimits(max_steps=Limit(0))
    result = esolangs.run(REFERENCE, "+.", limits=limits, isolated=isolated)
    assert result.bound == "max_steps"
    assert result.observation == esolangs.ExecutionResult("", 0, 0, 0, steps=0)
    assert esolangs.ExecutionLimits(max_memory=Limit(1), max_output=Limit(1)) == (
        esolangs.ExecutionLimits(max_memory=1, max_output=1)
    )
    for name in ("max_steps", "max_output", "max_memory"):
        with pytest.raises(esolangs.ArgumentError, match=name):
            esolangs.ExecutionLimits(**{name: Limit(-1)})


@pytest.mark.parametrize(
    "name", ["preparation_timeout", "execution_timeout", "total_timeout"]
)
def test_timeout_subclasses_cannot_change_the_validated_duration(name):
    class Duration(float):
        def __le__(self, _other):
            return False

        def __gt__(self, _other):
            return False

        def __float__(self):
            raise AssertionError("timeout backing value must be used")

    for value in (0.0, -1.0, 1e10):
        with pytest.raises(esolangs.ArgumentError, match=name):
            esolangs.ExecutionLimits(**{name: Duration(value)})
    limits = esolangs.ExecutionLimits(**{name: Duration(3.0)})
    assert type(getattr(limits, name)) is float
    assert getattr(limits, name) == 3.0


def test_duration_backing_values_reach_worker_and_debugger(monkeypatch):
    from esolangs.runtime import _controller

    class Duration(int):
        def __radd__(self, _other):
            raise AssertionError("timeout backing value must be used")

    limits = esolangs.ExecutionLimits(execution_timeout=Duration(3))
    api = esolangs.Language(REFERENCE)
    prepared = api.prepare("+.")
    assert prepared.run(limits=limits).unwrap().output == "\x01"

    clock = iter((0.0, 3.0))
    monkeypatch.setattr(_controller, "monotonic", clock.__next__)
    debugger = prepared.make_debugger()
    assert debugger.run(limits=limits) == "execution_timeout"
    assert debugger.observation == esolangs.ExecutionResult("", 0, 0, 0, steps=0)
