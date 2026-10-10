"""Tests for the Line Boolean generator: render -> extract -> simulate round-trips."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.interpreters.tape_based.line.extract import extract
from esolangs.interpreters.tape_based.line.simulate import (
    IO,
    compile_program,
    run_compiled,
)
from esolangs.raster import Raster, png
from esolangs.tools.line import line_boolean
from esolangs.tools.line.render import Node, render
from esolangs.tools.line.tree_layout import tree_extents
from tests.witness_tables import row_bits


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
        bits = row_bits(combo, n)
        io, outputs = _io(bits)
        run_compiled(program, io=io)
        assert outputs == [int(truth_table[combo])], (
            f"inputs={bits} expected {truth_table[combo]} got {outputs}"
        )


def _complement(table: str) -> str:
    """The table with every output flipped -- the same tree, other leaves."""
    return table.translate(str.maketrans("01", "10"))


def _topology(node: Node | None) -> str:
    """The fork skeleton of a pruned tree, with straight runs collapsed."""
    if node is None:
        return "."
    if node.op == "?":
        return f"?({_topology(node.zero)},{_topology(node.nonzero)})"
    return _topology(node.next) if node.next is not None else "L"


def _topology_representatives(n: int) -> list[str]:
    """One table per distinct fork topology over all ``2**2**n`` tables."""
    seen: dict[str, str] = {}
    for encoded in range(1 << (1 << n)):
        table = format(encoded, f"0{1 << n}b")
        seen.setdefault(_topology(line_boolean(table)), table)
    return list(seen.values())


class TestLineBoolean:
    """Generated decision trees, end to end through render -> extract -> simulate."""

    @pytest.mark.parametrize(
        ("table", "n"),
        [
            # Identity on one input: output follows the single bit.
            pytest.param("01", 1, id="identity_n1"),
            # NOT on one input: output is the inverted bit.
            pytest.param("10", 1, id="not_n1"),
            # AND over two inputs.
            pytest.param("0001", 2, id="and_n2"),
            # XOR over two inputs.
            pytest.param("0110", 2, id="xor_n2"),
            # The regression case: a 3-deep tree with an inward-turning arm.
            pytest.param("00010111", 3, id="majority_n3"),
        ],
    )
    def test_truth_table(self, tmp_path: Path, table: str, n: int) -> None:
        _check_truth_table(table, n, tmp_path)

    @pytest.mark.slow  # 5.2s: 32 input combinations through the renderer
    def test_parity_n5(self, tmp_path: Path) -> None:
        """5-input parity, past the ceiling this generator used to document."""
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
        """Every pruned shape survives render -> extract -> simulate."""
        representatives = _topology_representatives(3)
        assert len(representatives) == 26, (
            f"expected 26 fork topologies at n=3, found {len(representatives)}"
        )
        for table in representatives:
            _check_truth_table(table, 3, tmp_path)
            _check_truth_table(_complement(table), 3, tmp_path)


def test_line_generator_entry_points() -> None:
    import esolangs
    from esolangs.tools.line import balance
    from esolangs.tools.line import line as generate

    source = generate("01", scale=2)
    assert _evaluate("Line", source, inputs=1) == "01"
    balanced = balance("01", generate("01"))
    assert balanced.rows == esolangs.generate("Line", "01", balance=True).rows
    assert _evaluate("Line", balanced.to_png(), inputs=1) == "01"


@pytest.mark.medium
def test_six_inputs_keep_the_rendered_layout() -> None:
    """Past the small-tree cut-off both entry points draw through ``render``."""
    import esolangs

    table = "0110100110010110" * 4
    for balanced in (False, True):
        program = esolangs.generate("Line", table, balance=balanced)
        assert _evaluate("Line", program.to_png(), inputs=6) == table


@pytest.mark.medium
def test_line_extent_fast_path_preserves_merged_runs_and_shared_arms() -> None:
    leaf = Node("+", next=Node("+", next=Node("o")))
    for root in (leaf, Node("?", zero=leaf, nonzero=leaf), Node("?", zero=leaf)):
        compact = render(root, acyclic=True)
        legacy = render(root)
        assert render(root, acyclic=True, compact=False).pixels == legacy.pixels
        assert compact.width * compact.height <= legacy.width * legacy.height
        for value in (0, 1):
            sources = [
                Raster.from_png(png.write_grey(canvas.pixels))
                for canvas in (compact, legacy)
            ]
            assert esolangs.run("Line", sources[0], stdin=str(value)) == esolangs.run(
                "Line", sources[1], stdin=str(value)
            )
    assert (
        esolangs.run(
            "Line",
            Raster.from_png(png.write_grey(render(leaf, acyclic=True).pixels)),
            stdin="",
        )
        == "2"
    )
    leaf.goto = Node("o")
    with pytest.raises(ValueError, match="goto"):
        tree_extents(leaf)


@pytest.mark.medium
def test_shorter_stems_execute_every_small_function(tmp_path: Path) -> None:
    from esolangs.tools.line.small_tree import small_tree_canvas

    total = 0
    path = str(tmp_path / "shorter-stems.png")
    for inputs in range(1, 4):
        for encoded in range(2 ** (2**inputs)):
            table = f"{encoded:0{2**inputs}b}"
            node = line_boolean(table)
            previous = small_tree_canvas(node, compact=False)
            canvas = small_tree_canvas(node)
            assert canvas.width * canvas.height <= previous.width * previous.height
            canvas.save(path)
            program = compile_program(extract(path))
            for row in range(2**inputs):
                io, output = _io(list(map(int, f"{row:0{inputs}b}")))
                run_compiled(program, io=io)
                assert output == [int(table[row])]
            if inputs == 3:
                total += canvas.width * canvas.height
    assert total == 68_929_572


@pytest.mark.medium
@pytest.mark.parametrize("table", ["00010111", "00010101", "00100110", "01000101"])
def test_shorter_stems_balance_keeps_the_area_ceiling(table: str) -> None:
    from esolangs.tools.line.small_tree import small_tree_canvas

    previous = [
        small_tree_canvas(line_boolean(table, reverse=reverse), compact=False)
        for reverse in (False, True)
    ]
    old = min(previous, key=lambda c: (abs(c.width - c.height), c.width * c.height))
    image = esolangs.generate("Line", table, balance=True)
    assert len(image.rows[0]) * len(image.rows) <= old.width * old.height
    assert _evaluate("Line", image.to_png(), inputs=3) == table


def test_line_fast_path_avoids_subtree_walks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raster balancing renders the tree without revisiting a subtree."""
    import importlib

    from esolangs.tools.line import line_boolean
    from esolangs.tools.line.render import render

    module = importlib.import_module("esolangs.tools.line.render")

    def reject(*_args: object) -> None:
        raise AssertionError("tree renderer revisited a subtree")

    monkeypatch.setattr(module, "_has_goto", reject)
    monkeypatch.setattr(module, "_returns_to", reject)
    render(line_boolean("10010110"), acyclic=True)


@pytest.mark.medium
def test_shared_ancestor_return_executes_within_ledger(tmp_path: Path) -> None:
    """A consumed prefix bit selects one physical residual after returning."""
    from esolangs.tools.line import _render_node
    from esolangs.tools.line.render import _has_goto
    from esolangs.tools.line.shared import shared_canvas, shared_tree
    from tests.generator_support import assert_shared_program

    residual = "00010111" * 8
    table = residual * 3 + "0" * len(residual)
    plain = Raster(_render_node(line_boolean(table)))
    shared = shared_tree(table)
    assert shared is not None
    assert _has_goto(shared[0])
    draw = shared_canvas(shared[0], 10**12)
    assert draw is not None
    path = str(tmp_path / "shared.png")
    draw().save(path)
    program = compile_program(extract(path))
    for row in (0, 127, 128, 255):
        io, outputs = _io(list(map(int, f"{row:08b}")))
        run_compiled(program, io=io)
        assert outputs == [int(table[row])]
    assert_shared_program(
        "Line",
        table,
        plain,
        shared[1],
        lambda _: 47,
        size=lambda p: len(p.rows) * len(p.rows[0]),
    )


@pytest.mark.medium
def test_shared_return_retains_unshared_balance_and_scale() -> None:
    """The emitted return extracts at scale two and balancing retains old trees."""
    from esolangs.tools.line import _render_node, balance, line
    from esolangs.tools.line.shared import shared_canvas, shared_tree

    residual = "00010111" * 8
    table = residual * 3 + "1" * len(residual)
    program = line(table)
    plain = Raster(_render_node(line_boolean(table)))

    def score(raster):
        h, w = len(raster.rows), len(raster.rows[0])
        return abs(w - h), w * h, w

    assert score(balance(table, program)) <= score(balance(table, plain))
    # Force extraction instead of the retained generated graph.
    scaled = Raster(program.upscaled(2).rows)
    assert _evaluate("Line", scaled, inputs=8) == table
    shared = shared_tree(table)
    assert shared is not None
    assert shared_canvas(shared[0], 1) is None


def test_shared_return_refuses_an_interior_tip() -> None:
    """A matching residual inside the body's box retains the old tree."""
    from esolangs.tools.helpers import permute_truth_table
    from esolangs.tools.line.shared import shared_canvas, shared_tree

    residual = "01" * 16
    other = "0110" * 8
    table = residual * 4 + other + residual * 2 + other
    table = permute_truth_table(table, (1, 0, *range(2, 8)))
    shared = shared_tree(table)
    assert shared is not None
    assert shared_canvas(shared[0], 10**12) is None


def test_shared_candidate_preserves_the_small_tree_fallback() -> None:
    """An admissible return still loses to the five-input pixel layout."""
    from esolangs.tools.line import _grey_rows, line
    from esolangs.tools.line.shared import shared_tree
    from esolangs.tools.line.small_tree import small_tree_canvas

    residual = "01" * 4
    table = residual * 3 + "1" * len(residual)
    assert shared_tree(table) is not None
    expected = _grey_rows(small_tree_canvas(line_boolean(table)))
    image = line(table)
    assert len(image.rows) * len(image.rows[0]) <= len(expected) * len(expected[0])
    assert _evaluate("Line", Raster(line(table).rows), inputs=5) == table


@pytest.mark.medium
def test_balance_retains_a_more_balanced_shared_raster() -> None:
    """A shared return can improve both area and the old orientation's shape."""
    from esolangs.tools.line import _render_node, balance, line

    residual = "0010" * 16
    table = residual * 3 + "0" * len(residual)
    program = line(table)
    plain = Raster(_render_node(line_boolean(table)))
    balanced = balance(table, program)
    previous = balance(table, plain)
    h, w = len(balanced.rows), len(balanced.rows[0])
    old_h, old_w = len(previous.rows), len(previous.rows[0])
    assert abs(w - h) <= abs(old_w - old_h)
    assert w * h <= old_w * old_h
    assert _evaluate("Line", Raster(balanced.rows), inputs=8) == table
