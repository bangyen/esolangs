"""Shared public contracts, independent of language ownership."""

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
