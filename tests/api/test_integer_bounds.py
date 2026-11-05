"""Shared public contracts, independent of language ownership."""

import pytest

import esolangs
from esolangs import compat
from tests.support.pick import first
from tests.support.reference import REFERENCE


@pytest.mark.parametrize(
    "operation",
    [
        lambda huge: compat.run(REFERENCE, "", timeout=huge),
        lambda huge: compat.run(REFERENCE, "", timeout=-huge),
        lambda huge: compat.run(REFERENCE, "", isolated=True, max_output=-huge),
        lambda huge: compat.generate(REFERENCE, "01", width=-huge),
        lambda huge: esolangs.encode_inputs(REFERENCE, [huge]),
        lambda huge: esolangs.encode_inputs(REFERENCE, [True, huge]),
        lambda huge: compat.run(
            first(source_kind="raster"), esolangs.Raster((((0, 0, 0),),)), scale=-huge
        ),
        lambda huge: compat.run(REFERENCE, "", timeout={"value": huge}),
    ],
)
def test_oversized_integer_arguments_keep_public_errors(operation) -> None:
    with pytest.raises(esolangs.ArgumentError) as caught:
        operation(10**5000)
    assert len(str(caught.value)) < 400
