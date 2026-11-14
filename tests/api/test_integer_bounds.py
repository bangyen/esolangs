"""Shared public contracts, independent of language ownership."""

import sys

import pytest

import esolangs
from tests.support.pick import first
from tests.support.reference import REFERENCE


@pytest.mark.parametrize(
    "operation",
    [
        lambda huge: (
            esolangs.run(
                REFERENCE, "", limits=esolangs.ExecutionLimits(execution_timeout=huge)
            ).output
        ),
        lambda huge: esolangs.ExecutionLimits(max_memory=-huge),
        lambda huge: (
            esolangs.run(
                REFERENCE, "", limits=esolangs.ExecutionLimits(execution_timeout=-huge)
            ).output
        ),
        lambda huge: (
            esolangs.run(
                REFERENCE,
                "",
                isolated=True,
                limits=esolangs.ExecutionLimits(max_output=-huge),
            ).output
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
            ).output
        ),
        lambda huge: (
            esolangs.run(
                REFERENCE,
                "",
                limits=esolangs.ExecutionLimits(execution_timeout={"value": huge}),
            ).output
        ),
    ],
)
def test_oversized_integer_arguments_keep_public_errors(operation) -> None:
    with pytest.raises(esolangs.ArgumentError) as caught:
        operation(10**5000)
    assert len(str(caught.value)) < 400


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
    result = esolangs.execute(REFERENCE, "+.", limits=limits, isolated=isolated)
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
    assert prepared.run(limits=limits).output == "\x01"

    clock = iter((0.0, 3.0))
    monkeypatch.setattr(_controller, "monotonic", clock.__next__)
    debugger = prepared.make_debugger()
    assert debugger.run(limits=limits) == "execution_timeout"
    assert debugger.observation == esolangs.ExecutionResult("", 0, 0, 0, steps=0)
