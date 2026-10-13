"""Independent substring oracle for complete ordered residual sharing."""

from __future__ import annotations

import random

import pytest

from esolangs.languages.line.generator.forward import (
    centered_streaming_canvas,
    destination_canvas,
    forward_canvas,
    median_streaming_canvas,
    packed_streaming_canvas,
    streaming_canvas,
)
from esolangs.languages.line.generator.render import Node
from tests.support.witness_tables import dense, parity

_UNCAPPED = (
    forward_canvas,
    destination_canvas,
    streaming_canvas,
    centered_streaming_canvas,
    median_streaming_canvas,
)
_STREAMING = (
    streaming_canvas,
    centered_streaming_canvas,
    median_streaming_canvas,
    packed_streaming_canvas,
)


def _oracle(table: str) -> tuple[int, set[tuple[int, str]], bool]:
    """Return join count, prefix residuals, and packed-work rejection."""
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
    guard = sum(count * count for count in edges_into.values()) > 32 * len(table)
    return joins, states, guard


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


def _cases() -> list[str]:
    """Every n=2 and n=3 table, plus eight seeded tables each n=4..8."""
    cases = [format(value, "04b") for value in range(1 << 4)]
    cases += [format(value, "08b") for value in range(1 << 8)]
    for n in range(4, 9):
        for seed in range(8):
            rng = random.Random(7919 * n + seed)
            cases.append("".join(rng.choice("01") for _ in range(1 << n)))
    return cases


@pytest.mark.medium
@pytest.mark.parametrize("table", _cases())
def test_ordered_fold_matches_oracle_across_streaming_geometries(table: str) -> None:
    """Refusal matches the oracle, and every admitted fold is a bijection."""
    joins, states, guard = _oracle(table)
    built = streaming_canvas(table, 10**9)
    assert (built is not None) == (joins > 0)
    if built is None:
        for builder in _STREAMING:
            assert builder(table, 10**9) is None  # no repeated residual to fold
        return
    expected = states
    for builder in _STREAMING:
        candidate = builder(table, 10**9)
        if candidate is None:
            assert builder is packed_streaming_canvas
            assert guard
            continue
        assert set(_walk_states(candidate[0], table)) == expected


@pytest.mark.parametrize("table", ["0000", "1111", "00000000", "11111111"])
def test_constants_and_test_free_tables_offer_no_fold(table: str) -> None:
    """A never-repeating (here constant) residual has nothing to share."""
    joins, _, _ = _oracle(table)
    assert joins == 0
    for builder in _STREAMING:
        assert builder(table, 10**9) is None


@pytest.mark.medium
def test_rejection_allocates_no_raster(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rejected plan builds strokes without allocating a bitmap."""
    from esolangs.languages.line.generator import forward

    table = parity(8)
    for builder in _UNCAPPED:
        built = builder(table, 10**9)
        assert built is not None
        assert built[1].area > 1

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("a raster was allocated before area rejection")

    monkeypatch.setattr(forward, "Canvas", boom)
    for builder in _UNCAPPED:
        assert builder(table, 1) is None


@pytest.mark.medium
def test_uncapped_streaming_builds_dense12_despite_the_packed_work_guard() -> None:
    """The packed cap is a generation guard, not a sharing cutoff."""
    table = dense(12)
    joins, states, guard = _oracle(table)
    assert joins > 0
    assert guard
    assert packed_streaming_canvas(table, 10**12) is None
    built = streaming_canvas(table, 10**12)
    assert built is not None
    assert set(_walk_states(built[0], table)) == states


@pytest.mark.medium
@pytest.mark.parametrize("builder", _STREAMING)
@pytest.mark.parametrize(("unit", "scale"), [(8, 1), (20, 2)])
def test_complete_landing_layouts_execute_with_explicit_unit(
    builder, unit, scale, monkeypatch, tmp_path
) -> None:
    from esolangs.languages.line.interpreter.extract import extract
    from esolangs.languages.line.tests import test_boolean_line_forward as controls
    from esolangs.languages.line.tests.test_boolean_line_forward import _check

    monkeypatch.setattr(
        controls,
        "forward_canvas",
        lambda table, limit: builder(table, limit, unit=unit),
    )
    monkeypatch.setattr(controls, "extract", lambda path: extract(path, unit=unit))
    _check(f"{0xFAC748EF:032b}", tmp_path, scale=scale)


@pytest.mark.medium
def test_complete_fold_wins_fallback_tie_and_keeps_first_fold(monkeypatch) -> None:
    from copy import deepcopy
    from importlib import import_module

    from esolangs.languages.line.generator import _generate
    from esolangs.languages.line.tests.test_boolean_line_projection import _execute

    generator = import_module("esolangs.languages.line.generator")
    forward = import_module("esolangs.languages.line.generator.forward")
    table = "0110"
    built = streaming_canvas(table, 10**9)
    assert built is not None
    graph, plan = built
    other = deepcopy(graph)
    limits = []

    def first(_table, limit, **_kwargs):
        limits.append(limit)
        return (graph, plan) if plan.area < limit else None

    def second(_table, limit, **_kwargs):
        limits.append(limit)
        return (other, plan) if plan.area < limit else None

    # Supply an equally sized, executable fallback to exercise the tie policy.
    monkeypatch.setattr(generator, "small_tree_canvas", lambda *_args, **_kw: plan())
    monkeypatch.setattr(forward, "forward_canvas", first)
    monkeypatch.setattr(forward, "destination_canvas", second)
    for builder in _STREAMING:
        monkeypatch.setattr(forward, builder.__name__, lambda *_args, **_kw: None)
    _generate.cache_clear()
    try:
        image = generator.line(table)
        assert image._payload is graph  # noqa: SLF001 - check canonical selection
        assert limits == [plan.area + 1, plan.area]
        _execute(table, image, range(4))
    finally:
        _generate.cache_clear()


def _reverse_oracle(table: str) -> tuple[str, set[tuple[int, str]], int]:
    n = len(table).bit_length() - 1
    kept = [
        bit
        for bit in range(n)
        if any(
            table[row] != table[row ^ (1 << (n - 1 - bit))] for row in range(len(table))
        )
    ]
    reduced = "".join(
        table[
            sum(
                ((row >> (len(kept) - 1 - slot)) & 1) << (n - 1 - bit)
                for slot, bit in enumerate(reversed(kept))
            )
        ]
        for row in range(1 << len(kept))
    )
    states = {(0, reduced)} if len(set(reduced)) > 1 else set()
    edges = 0
    for depth in range(len(kept)):
        for _, sub in [key for key in states if key[0] == depth]:
            half = len(sub) // 2
            lo, hi = sub[:half], sub[half:]
            for child in (lo,) if lo == hi else (lo, hi):
                if len(set(child)) > 1:
                    edges += 1
                    states.add((depth + 1, child))
    return reduced, states, edges - max(0, len(states) - 1)


def _reverse_forks(head: Node, table: str) -> set[tuple[int, str]]:
    n = len(table).bit_length() - 1
    while head.op != "?":
        assert head.next is not None
        head = head.next
    identities = {}
    keys = {}
    for row in range(len(table)):
        node = head
        pointer = n - 1
        while node is not None:
            if node.op == "?":
                depth = n - 1 - pointer
                length = 1 << (n - depth)
                start = (row // length) * length
                key = depth, table[start : start + length]
                assert identities.setdefault(key, id(node)) == id(node)
                assert keys.setdefault(id(node), key) == key
                bit = (row >> pointer) & 1
                node = node.nonzero if bit else node.zero
            elif node.op == "<":
                pointer -= 1
                node = node.next
            elif node.op == "":
                node = node.next or node.goto
            else:
                assert node.op in {"+", "-", "o"}
                break
    return set(identities)


@pytest.mark.medium
@pytest.mark.parametrize("table", _cases())
def test_projected_reverse_fold_shares_every_conditional_residual(table) -> None:
    reduced, states, joins = _reverse_oracle(table)
    expected = {
        key
        for key in states
        if key[1][: len(key[1]) // 2] != key[1][len(key[1]) // 2 :]
    }
    for builder in (forward_canvas, destination_canvas):
        built = builder(table, 10**9)
        assert (built is not None) == (joins > 0)
        if built is not None:
            assert _reverse_forks(built[0], reduced) == expected


@pytest.mark.parametrize("table", ["00", "01", "10", "11"])
def test_one_input_tables_have_no_residual_merge(table) -> None:
    joins, _, _ = _oracle(table)
    assert joins == 0
    for builder in (*_UNCAPPED, packed_streaming_canvas):
        assert builder(table, 10**9) is None
