"""The decoder's guards against images that are not Line programs.

``extract.py``'s happy path is covered by the round trips in
``test_bf_to_line.py``, which draw a real program and read it back.  What
that can never reach is what the decoder does with a *degenerate* input: a
blank canvas, a blob that is not an arrowhead, a stroke whose legs are not
whole units.  Those arms are the ones a caller actually meets when handed
an arbitrary PNG, and every one of them here was unexecuted.

The unit helpers are called directly.  They take plain runs and lengths,
so reaching them through a drawing would mean constructing the pixels that
happen to produce the run -- a far less direct statement of the same fact.
"""

from __future__ import annotations

import pytest

from esolangs.line import extract
from esolangs.line.extract import _UNIT_TOLERANCE
from esolangs.line.mask import Mask


def _blank(height: int = 8, width: int = 8) -> Mask:
    return Mask(height, width)


class TestAnEmptyImage:
    """Every entry point that asks a blank mask for its bounds."""

    def test_cropping_a_blank_mask_is_refused(self) -> None:
        with pytest.raises(ValueError, match="no ink"):
            extract.crop_to_content(_blank())

    def test_a_blank_mask_has_unit_scale(self) -> None:
        """No ink means nothing to measure, so the scale is 1, not an error."""
        assert extract.detect_scale(_blank()) == 1

    def test_an_empty_blob_has_no_fill(self) -> None:
        assert extract._fill_ratio(_blank()) == 0.0  # noqa: SLF001


class TestUnitRounding:
    """A leg is a whole number of units, a stray pixel, or untrustworthy."""

    def test_an_exact_multiple_rounds_to_its_count(self) -> None:
        assert extract._round_units(30, 10) == 3  # noqa: SLF001

    def test_a_near_multiple_still_rounds(self) -> None:
        """Within the tolerance, so a drawn leg one pixel off still reads."""
        assert extract._round_units(31, 10) == 3  # noqa: SLF001

    def test_a_stray_pixel_is_zero_not_none(self) -> None:
        """0 is noise the scanner steps over; ``None`` would abort the match."""
        assert extract._round_units(1, 40) == 0  # noqa: SLF001

    def test_an_off_unit_length_is_untrusted(self) -> None:
        """Half a unit is an ordinary corner, not a kink leg."""
        assert extract._round_units(15, 10) is None  # noqa: SLF001

    def test_the_tolerance_is_what_decides(self) -> None:
        inside = int(10 * (1 + _UNIT_TOLERANCE)) - 1
        outside = int(10 * (1 + _UNIT_TOLERANCE)) + 2
        assert extract._round_units(inside, 10) is not None  # noqa: SLF001
        assert extract._round_units(outside, 10) is None  # noqa: SLF001


class TestTrailingNoise:
    """Telling a last opcode from one followed only by stray pixels."""

    def test_only_noise_after_the_last_opcode(self) -> None:
        runs = [(0, 30), (1, 1), (2, 1)]
        assert extract._only_noise_remains(runs, 1, 10)  # noqa: SLF001

    def test_a_real_leg_after_it_is_not_noise(self) -> None:
        runs = [(0, 30), (1, 1), (2, 30)]
        assert not extract._only_noise_remains(runs, 1, 10)  # noqa: SLF001

    def test_nothing_left_counts_as_noise(self) -> None:
        assert extract._only_noise_remains([(0, 30)], 1, 10)  # noqa: SLF001


class TestClassifyingNothing:
    """A stroke with no direction runs yields no opcodes."""

    def test_no_vertices_is_no_opcodes(self) -> None:
        assert extract.classify_ops([]) == []


def _vertices(runs: list[tuple[int, int]]) -> list:
    """Return vertices whose ``_direction_runs`` are exactly ``runs``.

    A run is ``(heading, length)``, and ``_direction_runs`` reads the
    heading off the first vertex and the length as the Chebyshev distance
    to the next -- so advancing along one axis produces any run list, which
    is what lets the scanner's rejection arms be stated as data.
    """
    from esolangs.line.lattice import Vertex

    out = []
    x = 0
    for heading, length in runs:
        out.append(Vertex(0, x, heading))
        x += length
    out.append(Vertex(0, x, None))
    return out


class TestTheScannerRejects:
    """Runs that are not kink legs.

    The round trips in ``test_bf_to_line.py`` are the positive control:
    they draw real opcodes and read them back, so what is left to state is
    what the scanner does with a leg it cannot use.  Each case below is a
    different way to fail, and none was executed.
    """

    def test_a_stray_pixel_between_legs_is_skipped(self) -> None:
        """A run rounding to zero units advances without changing heading."""
        assert extract.classify_ops(_vertices([(0, 40), (1, 1)])) == []

    def test_an_off_unit_turn_is_an_ordinary_corner(self) -> None:
        """Half a unit cannot be a leg, so it re-bases the heading instead."""
        assert extract.classify_ops(_vertices([(0, 40), (1, 30)])) == []

    def test_a_signature_that_runs_out_of_runs_does_not_match(self) -> None:
        """One leg of a two-leg opcode, with the stroke ending after it."""
        assert extract.classify_ops(_vertices([(0, 40), (1, 20)])) == []

    def test_a_signature_whose_later_leg_is_off_unit_does_not_match(self) -> None:
        """The second leg is 1.5 units, so the candidate is abandoned."""
        calls = extract.classify_ops(_vertices([(0, 40), (1, 20), (6, 30)]))
        assert [call.op for call in calls] == ["+"]
