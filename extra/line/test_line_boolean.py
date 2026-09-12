r"""Tests for line_boolean.py: render -> extract -> simulate."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest
from extract import extract
from line_boolean import line_boolean
from render import render
from simulate import IO, compile_program, run_compiled


def _io(inputs: list[int]) -> tuple[IO, list[int]]:
    outputs: list[int] = []
    values: Iterator[int] = iter(inputs)
    return IO(read=values.__next__, write=outputs.append), outputs


def _check_truth_table(
    truth_table: str, n: int, tmp_path: Path, rows: Iterable[int] | None = None
) -> None:
    path = str(tmp_path / "bool.png")
    render(line_boolean(truth_table)).save(path)
    program = compile_program(extract(path))
    for combo in range(2**n) if rows is None else rows:
        bits = [(combo >> (n - 1 - i)) & 1 for i in range(n)]
        io, outputs = _io(bits)
        run_compiled(program, io=io)
        assert outputs == [int(truth_table[combo])], (
            f"inputs={bits} expected {truth_table[combo]} got {outputs}"
        )


class TestLineBoolean:
    r"""Generated decision trees, end to end through render -> extract ->."""

    def test_identity_n1(self, tmp_path: Path) -> None:
        r"""Identity on one input: output follows the single bit."""
        _check_truth_table("01", 1, tmp_path)

    def test_not_n1(self, tmp_path: Path) -> None:
        r"""NOT on one input: output is the inverted bit."""
        _check_truth_table("10", 1, tmp_path)

    def test_and_n2(self, tmp_path: Path) -> None:
        r"""AND over two inputs."""
        _check_truth_table("0001", 2, tmp_path)

    def test_xor_n2(self, tmp_path: Path) -> None:
        r"""XOR over two inputs."""
        _check_truth_table("0110", 2, tmp_path)

    def test_majority_n3(self, tmp_path: Path) -> None:
        r"""The regression case: a 3-deep tree with an inward-turning arm."""
        _check_truth_table("00010111", 3, tmp_path)

    @pytest.mark.slow  # 5.2s: 32 input combinations.
    def test_parity_n5(self, tmp_path: Path) -> None:
        r"""5-input parity, past the ceiling this generator used to document."""
        _check_truth_table("01101001100101101001011001101001", 5, tmp_path)

    @pytest.mark.slow  # 7s: all 256 rendered-tree.
    def test_parity_n8(self, tmp_path: Path) -> None:
        r"""8-input parity reaches every leaf through the real PNG round trip."""
        _check_truth_table(
            "".join(str(bits.bit_count() % 2) for bits in range(2**8)),
            8,
            tmp_path,
        )

    # n=9 is sampled, and n=10 is.
    # combination, at 13.4s and.
    # covered not one further line.
    # simulate -- the tree is one.
    # every leaf of it, so a wider.
    # drawing.
    # the rows below are the ones.
    # single-bit index, both.
    # boundary -- so a mis-sized.
    # showing up as a larger.
    # .
    # Sampling the rows is not what.
    # not a speed measure: at n=9.
    # 0.6s of execution, so the.
    # whatever the rows.
    # chosen so the remaining arity.
    # rendering.
    @pytest.mark.slow  # 13s: one n=9 drawing,.
    def test_parity_n9_on_boundary_rows(self, tmp_path: Path) -> None:
        r"""9-input parity is checked where an arm's size can go wrong."""
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

    def test_invalid_length_rejected(self) -> None:
        r"""A truth table whose length is not a power of two is rejected."""
        with pytest.raises(ValueError, match="power-of-two"):
            line_boolean("010")

    def test_invalid_characters_rejected(self) -> None:
        r"""A truth table containing anything but 0/1 is rejected."""
        with pytest.raises(ValueError, match="only '0' and '1'"):
            line_boolean("0102")
