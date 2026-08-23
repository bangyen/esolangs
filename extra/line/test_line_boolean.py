"""Tests for line_boolean.py: render -> extract -> simulate round-trips.

Run via: uv run --with pillow --with numpy --with scipy --with scikit-image
--with pytest pytest test_line_boolean.py

Covers n=1 through n=3 across every input combination, plus the specific
geometry bug this module's development caught: render.py's `_layout` used
to space sibling fork arms *outward* with absolute nesting depth, which
looks intuitively safer but is backwards for a tree that turns 90 degrees
at every fork -- a deeper arm's own children turn back toward the
*original* heading and, given enough length, cross an ancestor fork's own
line.  n=1 and n=2 (single fork level) cannot expose this at all; n=3 is
the first case with a re-converging inward turn, so it is the regression
test for the fix (`_BRANCH_SPACING` scaling by 2**remaining-depth instead
of by absolute depth -- see render.py's own comment for the full story).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from extract import extract
from line_boolean import line_boolean
from render import render
from simulate import IO, run


def _io(inputs: list[int]) -> tuple[IO, list[int]]:
    outputs: list[int] = []
    values: Iterator[int] = iter(inputs)
    return IO(read=values.__next__, write=outputs.append), outputs


def _check_truth_table(truth_table: str, n: int, tmp_path: Path) -> None:
    path = str(tmp_path / "bool.png")
    render(line_boolean(truth_table)).save(path)
    tree = extract(path)
    for combo in range(2**n):
        bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
        io, outputs = _io(bits)
        run(tree, io=io)
        assert outputs == [int(truth_table[combo])], (
            f"inputs={bits} expected {truth_table[combo]} got {outputs}"
        )


class TestLineBoolean:
    """Generated decision trees, end to end through render -> extract -> simulate."""

    def test_identity_n1(self, tmp_path: Path) -> None:
        """Identity on one input: output follows the single bit."""
        _check_truth_table("01", 1, tmp_path)

    def test_not_n1(self, tmp_path: Path) -> None:
        """NOT on one input: output is the inverted bit."""
        _check_truth_table("10", 1, tmp_path)

    def test_and_n2(self, tmp_path: Path) -> None:
        """AND over two inputs."""
        _check_truth_table("0001", 2, tmp_path)

    def test_xor_n2(self, tmp_path: Path) -> None:
        """XOR over two inputs."""
        _check_truth_table("0110", 2, tmp_path)

    def test_majority_n3(self, tmp_path: Path) -> None:
        """The regression case: a 3-deep tree with an inward-turning arm."""
        _check_truth_table("00010111", 3, tmp_path)

    def test_parity_n5(self, tmp_path: Path) -> None:
        """5-input parity, past the ceiling this generator used to document.

        `line_boolean.py` recorded a practical limit of n<=4, with n=5
        projected at roughly 35000x17000px and called impractical.  That was
        an artifact of `render._fork_depth`'s fork-counting arm spacing, not
        of decision trees: with extent-based spacing n=5 renders at 4000x2620
        and extracts in about a second.  Pinned here at n=5 rather than the
        n=7 that also passes, to keep the suite fast (n=7 spends ~9s in
        extract plus execution) while still covering two levels past where
        coverage used to stop -- deep enough that a regression in arm sizing
        shows up as a real failure here rather than only as a larger drawing.

        Parity is the useful table at this depth: every one of the 32 input
        combinations reaches a distinct leaf, so a mis-sized arm anywhere in
        the tree changes an answer rather than hiding in an unvisited branch.
        """
        _check_truth_table("01101001100101101001011001101001", 5, tmp_path)

    def test_invalid_length_rejected(self) -> None:
        """A truth table whose length is not a power of two is rejected."""
        with pytest.raises(ValueError, match="power-of-two"):
            line_boolean("010")

    def test_invalid_characters_rejected(self) -> None:
        """A truth table containing anything but 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            line_boolean("0102")
