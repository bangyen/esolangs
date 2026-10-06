"""One-column layouts execute through the public input and answer interfaces."""

import pytest

import esolangs


@pytest.mark.parametrize("language", ["Befunge", "Fish", "Super SNUSP", "thisthat"])
def test_xor_has_one_column(language: str) -> None:
    assert max(map(len, esolangs.generate(language, "0110", 1).splitlines())) == 1
