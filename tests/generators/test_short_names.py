"""Shared identifier numbering."""

import pytest

from esolangs.tools.helpers import short_name


@pytest.mark.parametrize(
    ("index", "expected"),
    [(0, "a"), (1, "b"), (2, "aa"), (5, "bb"), (6, "aaa"), (13, "bbb")],
)
def test_names_cross_length_boundaries(index: int, expected: str) -> None:
    assert short_name(index, "ab") == expected


@pytest.mark.parametrize(("index", "alphabet"), [(-1, "ab"), (0, "")])
def test_invalid_namespace_arguments_fail(index: int, alphabet: str) -> None:
    with pytest.raises(ValueError, match="nonnegative index and nonempty alphabet"):
        short_name(index, alphabet)
