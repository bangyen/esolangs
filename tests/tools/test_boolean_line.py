"""Tests for the Line Boolean generator: render -> extract -> simulate round-trips.

Run via: uv run pytest tests/tools/test_boolean_line.py

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

from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

from esolangs.line.extract import extract
from esolangs.line.render import Node, render
from esolangs.line.simulate import IO, compile_program, run_compiled
from esolangs.tools.line import line_boolean


def _forks(node: Node | None) -> int:
    """Count the ``?`` tests in a generated (loop-free) tree."""
    if node is None:
        return 0
    if node.op == "?":
        return 1 + _forks(node.zero) + _forks(node.nonzero)
    return _forks(node.next)


def _io(inputs: list[int]) -> tuple[IO, list[int]]:
    outputs: list[int] = []
    values: Iterator[int] = iter(inputs)
    return IO(read=values.__next__, write=outputs.append), outputs


def _check_truth_table(
    truth_table: str, n: int, tmp_path: Path, rows: Iterable[int] | None = None
) -> None:
    path = str(tmp_path / "bool.png")
    render(line_boolean(truth_table), acyclic=True).save(path)
    program = compile_program(extract(path))
    for combo in range(2**n) if rows is None else rows:
        bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
        io, outputs = _io(bits)
        run_compiled(program, io=io)
        assert outputs == [int(truth_table[combo])], (
            f"inputs={bits} expected {truth_table[combo]} got {outputs}"
        )


def _complement(table: str) -> str:
    """The table with every output flipped -- the same tree, other leaves."""
    return table.translate(str.maketrans("01", "10"))


def _topology(node: Node | None) -> str:
    """The fork skeleton of a pruned tree, with straight runs collapsed.

    Two tables share a topology when they nest the same way, whatever their
    leaves print.  That is the part `render._layout` sizes arms from.
    """
    if node is None:
        return "."
    if node.op == "?":
        return f"?({_topology(node.zero)},{_topology(node.nonzero)})"
    return _topology(node.next) if node.next is not None else "L"


def _topology_representatives(n: int) -> list[str]:
    """One table per distinct fork topology over all ``2**2**n`` tables.

    The first table reaching a topology wins it; the enumeration never
    renders, so covering the whole space here is cheap.
    """
    seen: dict[str, str] = {}
    for encoded in range(1 << (1 << n)):
        table = format(encoded, f"0{1 << n}b")
        seen.setdefault(_topology(line_boolean(table)), table)
    return list(seen.values())


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

    @pytest.mark.slow  # 5.2s: 32 input combinations through the renderer
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

    @pytest.mark.slow  # 7s: all 256 rendered-tree executions
    def test_parity_n8(self, tmp_path: Path) -> None:
        """8-input parity reaches every leaf through the real PNG round trip."""
        _check_truth_table(
            "".join(str(bits.bit_count() % 2) for bits in range(2**8)),
            8,
            tmp_path,
        )

    # n=9 is sampled, and n=10 is gone.  Both used to sweep every input
    # combination, at 13.4s and 29.0s; measured against the n<=8 set they
    # covered not one further line of render, extract, lattice, mask, png or
    # simulate -- the tree is one recursive shape and n=8 already reaches
    # every leaf of it, so a wider arity re-runs the same code on a bigger
    # drawing.  What a ninth input does add is a carry the eighth does not:
    # the rows below are the ones where the arm sizing can go wrong -- every
    # single-bit index, both extremes, and both sides of each power-of-two
    # boundary -- so a mis-sized arm still fails here rather than only
    # showing up as a larger picture.
    #
    # Sampling the rows is not what makes this cheap, and the row list is
    # not a speed measure: at n=9 the run is 11.6s of `extract` against
    # 0.6s of execution, so the drawing is the cost and it is paid once
    # whatever the rows.  Dropping n=10 is the saving (29.0s); the rows are
    # chosen so the remaining arity still fails loudly rather than merely
    # rendering.
    @pytest.mark.slow  # 13s: one n=9 drawing, extracted once, at its boundary rows
    def test_parity_n9_on_boundary_rows(self, tmp_path: Path) -> None:
        """9-input parity is checked where an arm's size can go wrong."""
        n = 9
        rows = {0, 2**n - 1}
        rows.update(1 << i for i in range(n))
        for edge in (2**i for i in range(1, n)):
            rows.update({edge - 1, edge, edge + 1} & set(range(2**n)))
        _check_truth_table(
            "".join(str(bits.bit_count() % 2) for bits in range(2**n)),
            n,
            tmp_path,
            rows=sorted(rows),
        )

    def test_constants_test_nothing(self, tmp_path: Path) -> None:
        """The positive control: a constant reads its inputs and prints."""
        for table in ("0" * 8, "1" * 8):
            assert _forks(line_boolean(table)) == 0
            _check_truth_table(table, 3, tmp_path)
        canvas = render(line_boolean("0" * 16))
        assert len(canvas.pixels) * len(canvas.pixels[0]) < 100_000

    def test_only_dependent_levels_are_tested(self, tmp_path: Path) -> None:
        """A level whose halves agree is read but never tested."""
        assert _forks(line_boolean("00001111")) == 1  # the first input alone
        assert _forks(line_boolean("01010101")) == 1  # the last input alone
        assert _forks(line_boolean("00010011")) == 4  # the full tree has 7
        _check_truth_table("00010011", 3, tmp_path)
        _check_truth_table("01010101", 3, tmp_path)

    @pytest.mark.slow  # ~8s: one drawing per fork topology, both polarities
    def test_every_pruned_shape_survives(self, tmp_path: Path) -> None:
        """Every pruned shape survives render -> extract -> simulate.

        This used to render all 256 three-input tables, at ~40s the most
        expensive test in the suite.  All 256 are distinct *drawings*, so
        there was no duplicate to delete -- but they carry only 26 fork
        topologies between them, and the topology (which subtrees survive
        pruning, how deep the arms nest) is what `_layout` sizes arms from.
        So the sweep enumerates topologies and renders one representative of
        each, plus its complement to flip every leaf at once -- leaf values
        set the length of the `+` run before each `o`, and so an arm's
        extent.  Enumerating is `line_boolean` alone, which does no drawing;
        only the 52 representatives pay for render -> extract.  A generator
        that grows a new topology is covered the day it does, without this
        test being edited: it pins the contract, not a list of tables.

        What this does *not* buy is arm-spacing coverage, and the exhaustive
        version did not buy it either.  Against five mutants of the spacing
        arithmetic (`_BRANCH_SPACING` at 4, 2 and 1; the `reach_back` term
        dropped and halved) all 256 tables passed every one.  The same
        mutants are caught -- 31 failures for `_BRANCH_SPACING = 1` -- by
        `test_parity_n5`/`n8`/`n9_on_boundary_rows` and by the loop-back
        shapes in `test_bf_to_line.py`.  n=3 drawings are simply too small
        for a spacing error to close a gap.  Those tests are where the
        geometry regression in the module docstring is actually pinned; this
        one pins that the generator answers correctly through the PNG for
        every shape it can emit.
        """
        representatives = _topology_representatives(3)
        assert len(representatives) == 26, (
            f"expected 26 fork topologies at n=3, found {len(representatives)}"
        )
        for table in representatives:
            _check_truth_table(table, 3, tmp_path)
            _check_truth_table(_complement(table), 3, tmp_path)

    def test_invalid_length_rejected(self) -> None:
        """A truth table whose length is not a power of two is rejected."""
        with pytest.raises(ValueError, match="power-of-two"):
            line_boolean("010")

    def test_invalid_characters_rejected(self) -> None:
        """A truth table containing anything but 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            line_boolean("0102")


def test_language_package_retains_generator_entry_points() -> None:
    import esolangs
    from esolangs.line import balance, generate

    source = generate("01", scale=2)
    assert esolangs.evaluate("Line", source, inputs=1) == "01"
    balanced = balance("01", generate("01"))
    assert balanced.to_png() == esolangs.generate("Line", "01", balance=True).to_png()
    assert esolangs.evaluate("Line", balanced.to_png(), inputs=1) == "01"
