"""Independent substring oracle for complete ordered residual sharing."""

from __future__ import annotations

import random

import pytest

from esolangs.languages.line.generator.forward import streaming_canvas
from esolangs.languages.line.generator.layout import Node
from tests.support.witness_tables import parity


def _oracle(table: str) -> tuple[int, set[tuple[int, str]]]:
    """Return join count and prefix residuals."""
    root = (0, table)
    states = {root}
    frontier = {root}
    edges_into: dict[int, int] = {}
    while frontier:
        nxt: set[tuple[int, str]] = set()
        for depth, sub in frontier:
            half = len(sub) // 2
            if not half:
                continue
            lo, hi = sub[:half], sub[half:]
            arms = (lo,) if lo == hi else (lo, hi)
            edges_into[depth + 1] = edges_into.get(depth + 1, 0) + len(arms)
            for child in arms:
                key = (depth + 1, child)
                if key not in states:
                    states.add(key)
                    nxt.add(key)
        frontier = nxt
    joins = sum(edges_into.values()) - (len(states) - 1)
    return joins, states


def _walk_states(head: Node, table: str) -> dict[tuple[int, str], int]:
    """Return one node identity per residual, including output terminals."""
    n = len(table).bit_length() - 1
    key_to_id: dict[tuple[int, str], int] = {}
    id_to_key: dict[int, tuple[int, str]] = {}
    stack = [(head, 0, 0)]
    while stack:
        node, depth, prefix = stack.pop()
        assert node is not None
        length = 1 << (n - depth)
        sub = table[prefix * length : (prefix + 1) * length]
        key = (depth, sub)
        ident = id(node)
        assert key_to_id.setdefault(key, ident) == ident, f"two nodes for {key}"
        assert id_to_key.setdefault(ident, key) == key, (
            "distinct residuals share a node"
        )
        if depth == n:
            ops = []
            while node is not None:
                ops.append(node.op)
                node = node.next
            assert ops == [">", *(["+"] if sub == "1" else []), "o"]
            continue
        assert node.op == "i"
        sel = node.next
        assert sel is not None
        half = len(sub) // 2
        is_fork = sub[:half] != sub[half:]
        assert sel.op == ("?" if is_fork else "")
        arms = [(0, sel.zero), (1, sel.nonzero)] if is_fork else [(0, sel.next)]
        for bit, child in arms:
            if child is not None and child.op == "" and child.goto is not None:
                child = child.goto
            assert child is not None
            stack.append((child, depth + 1, prefix * 2 + bit))
    return key_to_id


def _shape(table: str) -> tuple[object, ...]:
    """Return which residuals are equal at each depth, and the first bit."""
    patterns: list[tuple[int, ...]] = []
    size = len(table)
    while size > 1:
        first: dict[str, int] = {}
        subs = (table[i : i + size] for i in range(0, len(table), size))
        patterns.append(tuple(first.setdefault(sub, len(first)) for sub in subs))
        size //= 2
    return (*patterns, table[0])


def _cases() -> list[str]:
    """One n=2 or n=3 table per residual shape, plus one seeded table n=4..8.

    The oracle and the fold see only which residuals are equal, so the 272
    exhaustive tables collapse to these classes with the same branch coverage.
    """
    shapes: dict[tuple[object, ...], str] = {}
    for width in (4, 8):
        for value in range(1 << width):
            table = format(value, f"0{width}b")
            shapes.setdefault(_shape(table), table)
    cases = list(shapes.values())
    for n in range(4, 9):
        rng = random.Random(7919 * n)
        cases.append("".join(rng.choice("01") for _ in range(1 << n)))
    return cases


@pytest.mark.medium
@pytest.mark.parametrize("table", _cases())
def test_ordered_fold_matches_oracle(table: str) -> None:
    """Refusal matches the oracle, and every admitted fold is a bijection."""
    joins, states = _oracle(table)
    built = streaming_canvas(table, 10**9)
    assert (built is not None) == (joins > 0)
    if built is not None:
        assert set(_walk_states(built[0], table)) == states


@pytest.mark.parametrize(
    "table", ["00", "01", "10", "11", "0000", "1111", "00000000", "11111111"]
)
def test_tables_without_a_repeated_residual_offer_no_fold(table: str) -> None:
    """Constants and one-input tables have no residual to share."""
    joins, _ = _oracle(table)
    assert joins == 0
    assert streaming_canvas(table, 10**9) is None


@pytest.mark.medium
def test_rejection_allocates_no_raster(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rejected plan builds strokes without allocating a bitmap."""
    from esolangs.languages.line.generator import shared

    table = parity(8)
    built = streaming_canvas(table, 10**9)
    assert built is not None
    assert built[1].area > 1

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a raster was allocated before area rejection")

    monkeypatch.setattr(shared, "Canvas", boom)
    assert streaming_canvas(table, 1) is None


@pytest.mark.medium
@pytest.mark.parametrize(("unit", "scale"), [(8, 1), (20, 2)])
def test_complete_landing_layouts_execute_with_explicit_unit(
    unit, scale, monkeypatch, tmp_path
) -> None:
    from esolangs.languages.line.interpreter.extract import extract
    from esolangs.languages.line.tests import test_boolean_line_forward as controls
    from esolangs.languages.line.tests.test_boolean_line_forward import _check

    monkeypatch.setattr(
        controls,
        "forward_canvas",
        lambda table, limit: streaming_canvas(table, limit, unit=unit),
    )
    monkeypatch.setattr(controls, "extract", lambda path: extract(path, unit=unit))
    _check(f"{0xFAC748EF:032b}", tmp_path, scale=scale)


@pytest.mark.medium
def test_complete_fold_wins_fallback_tie(monkeypatch) -> None:
    from importlib import import_module

    from esolangs.languages.line.generator import _generate
    from esolangs.languages.line.tests.test_boolean_line_projection import _execute

    generator = import_module("esolangs.languages.line.generator")
    table = "0110"
    built = streaming_canvas(table, 10**9)
    assert built is not None
    graph, plan = built
    limits = []

    def first(_table, limit, **_kwargs):
        limits.append(limit)
        return (graph, plan) if plan.area < limit else None

    # Supply an equally sized, executable fallback to exercise the tie policy.
    monkeypatch.setattr(generator, "small_tree_canvas", lambda *_args, **_kw: plan())
    monkeypatch.setattr(generator, "streaming_canvas", first)
    _generate.cache_clear()
    try:
        image = generator.line(table)
        assert image._payload is graph  # noqa: SLF001 - check canonical selection
        assert limits == [plan.area + 1]
        _execute(table, image, range(4))
    finally:
        _generate.cache_clear()
