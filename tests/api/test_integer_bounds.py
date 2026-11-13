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
