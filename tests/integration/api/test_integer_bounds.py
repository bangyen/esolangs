"""Shared public contracts, independent of language ownership."""

import pytest

import esolangs
from tests.reference import REFERENCE
from tests.support.pick import first


@pytest.mark.parametrize(
    "operation",
    [
        lambda huge: esolangs.run(REFERENCE, "", timeout=huge),
        lambda huge: esolangs.run(REFERENCE, "", timeout=-huge),
        lambda huge: esolangs.run(REFERENCE, "", isolated=True, max_output=-huge),
        lambda huge: esolangs.generate(REFERENCE, "01", width=-huge),
        lambda huge: esolangs.encode_inputs(REFERENCE, [huge]),
        lambda huge: esolangs.encode_inputs(REFERENCE, [True, huge]),
        lambda huge: esolangs.run(
            first(source_kind="raster"), esolangs.Raster((((0, 0, 0),),)), scale=-huge
        ),
        lambda huge: esolangs.run(REFERENCE, "", timeout={"value": huge}),
    ],
)
def test_oversized_integer_arguments_keep_public_errors(operation):
    with pytest.raises(esolangs.ArgumentError) as caught:
        operation(10**5000)
    assert len(str(caught.value)) < 400
