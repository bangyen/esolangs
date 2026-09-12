"""Tests for mask.py.

Run via: uv run --with pytest pytest test_mask.py

Mask replaced numpy boolean arrays (see the dependency notes in extract.py).
The row-bitmask representation makes two things easy to get wrong, and both
are covered here: Python ints are unbounded, so anything involving ``~`` or a
left shift can leak bits past the canvas width; and the bit-twiddling
shortcuts (lowest-set-bit walks, block-uniformity collapses) have edge cases
at empty rows and at the last, possibly partial, block.
"""

from __future__ import annotations

import pytest
from mask import Mask, from_grey


def test_get_and_set_round_trip() -> None:
    """Setting a pixel makes it read back, and clearing it undoes that."""
    mask = Mask(3, 5)
    assert mask.sum() == 0
    mask[1, 2] = True
    assert list(mask.nonzero()) == [(1, 2)]
    assert mask.sum() == 1
    mask[1, 2] = False
    assert mask.sum() == 0


def test_from_rows_reads_row_major() -> None:
    """``from_rows`` maps '#' to ink at the position it appears in the string."""
    mask = Mask.from_rows([".#.", "..#"])
    assert mask.shape == (2, 3)
    assert list(mask.nonzero()) == [(0, 1), (1, 2)]


def test_any_and_sum_on_a_blank_mask() -> None:
    """A blank mask has no ink and no bounding box."""
    mask = Mask(4, 4)
    assert not mask.any()
    assert mask.sum() == 0
    assert mask.bounds() is None


def test_bounds_is_tight_and_inclusive() -> None:
    """The box hugs the ink, with bottom and right inside it."""
    mask = Mask.from_rows(
        [
            ".....",
            "..#..",
            ".#...",
            "...#.",
            ".....",
        ]
    )
    assert mask.bounds() == (1, 1, 3, 3)


def test_invert_does_not_leak_past_the_width() -> None:
    """Inverting keeps rows inside the canvas rather than going negative.

    A bare ``~`` on a Python int yields a negative value with unboundedly many
    leading one-bits, which would make ``sum`` and ``bounds`` nonsense.
    """
    mask = Mask.from_rows(["#..", "..."])
    flipped = ~mask
    assert all(row >= 0 for row in flipped.rows)
    assert flipped.sum() == 5
    assert list(flipped.nonzero()) == [(0, 1), (0, 2), (1, 0), (1, 1), (1, 2)]


def test_bitwise_ops_combine_pixelwise() -> None:
    """AND, OR and XOR act pixel by pixel."""
    a = Mask.from_rows(["##.", "..."])
    b = Mask.from_rows([".##", "..."])
    assert list((a & b).nonzero()) == [(0, 1)]
    assert list((a | b).nonzero()) == [(0, 0), (0, 1), (0, 2)]
    assert list((a ^ b).nonzero()) == [(0, 0), (0, 2)]


def test_bitwise_ops_reject_a_shape_mismatch() -> None:
    """Combining differently-shaped masks is a bug, not a broadcast."""
    with pytest.raises(ValueError, match="shapes differ"):
        _ = Mask(2, 2) & Mask(2, 3)


def test_erode_keeps_only_fully_surrounded_ink() -> None:
    """Only a pixel whose whole 8-neighborhood is ink survives.

    The centre of a solid 3x3 block survives; a 1px-wide line does not, which
    is the property find_cursor relies on to pick the arrowhead out of a
    drawing made of 1px strokes.
    """
    block = Mask.from_rows(["###", "###", "###"])
    # The centre is the only pixel with all 8 neighbours inside the block.
    assert list(block.erode().nonzero()) == [(1, 1)]

    line = Mask.from_rows(["...", "###", "..."])
    assert not line.erode().any()


def test_erode_treats_the_border_as_background() -> None:
    """Ink touching the canvas edge has no neighbours there, so it erodes."""
    full = Mask.from_rows(["##", "##"])
    assert not full.erode().any()


def test_crop_extracts_a_subrectangle() -> None:
    """Cropping takes the requested window and shifts it to the origin."""
    mask = Mask.from_rows(
        [
            "....",
            ".##.",
            ".#..",
            "....",
        ]
    )
    cropped = mask.crop(1, 1, 2, 2)
    assert cropped.shape == (2, 2)
    assert list(cropped.nonzero()) == [(0, 0), (0, 1), (1, 0)]


def test_subsample_takes_every_step_th_pixel() -> None:
    """Subsampling a 2x pixel-replicated image recovers the original."""
    original = Mask.from_rows(["#.", ".#"])
    doubled = Mask.from_rows(["##..", "##..", "..##", "..##"])
    assert doubled.subsample(2) == original


def test_subsample_honours_its_offset() -> None:
    """The offset picks which pixel within each block is sampled."""
    mask = Mask.from_rows(["#.", ".#"])
    assert list(mask.subsample(2, 0, 0).nonzero()) == [(0, 0)]
    assert list(mask.subsample(2, 1, 1).nonzero()) == [(0, 0)]


def test_equality_compares_shape_as_well_as_pixels() -> None:
    """Two blank masks of different sizes are not equal."""
    assert Mask(2, 2) == Mask(2, 2)
    assert Mask(2, 2) != Mask(2, 3)
    assert Mask(2, 2) != "not a mask"


def test_copy_is_independent() -> None:
    """Mutating a copy leaves the original alone."""
    mask = Mask.from_rows(["#.", ".."])
    clone = mask.copy()
    clone[1, 1] = True
    assert not mask[1, 1]


def test_from_grey_thresholds_at_mid_grey() -> None:
    """Levels below the threshold are ink; the threshold itself is not."""
    mask = from_grey([bytearray([0, 127, 128, 255])])
    assert list(mask.nonzero()) == [(0, 0), (0, 1)]
