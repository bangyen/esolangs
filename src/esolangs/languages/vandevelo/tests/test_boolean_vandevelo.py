"""Tests for the Vandevelo boolean generator."""

import importlib
from itertools import product

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.languages.vandevelo.generator import (
    _SAMPLES,
    _best,
    _ensure_popular,
    _Node,
    _pairs,
    vandevelo,
)
from esolangs.languages.vandevelo.interpreter import _Machine
from esolangs.vm import run_until_halt_or_cycle


def _result(program: str, bits: tuple[int, ...]) -> str:
    io = ScriptedIO("".join(f"{bit}\n" for bit in bits))
    return "0" if run_until_halt_or_cycle(_Machine(program, io)) else "1"


def test_xor_executes_every_generated_row() -> None:
    program = vandevelo("0110")
    results = (_result(program, bits) for bits in product(range(2), repeat=2))
    assert "".join(results) == "0110"


def test_constant_still_reads_every_input() -> None:
    program = vandevelo("00000000")
    io = ScriptedIO("0\n1\n0\n")
    assert run_until_halt_or_cycle(_Machine(program, io))
    assert io.reads == 3


@pytest.mark.parametrize(
    ("table", "expected"),
    [
        pytest.param("0001", "b? :: a? :: loop?", id="one_rows_are_named_cubes"),
        pytest.param("11111111", "loop?", id="constant_one_needs_no_guards"),
        pytest.param("00001111", "a? :: loop?", id="constant_subtree_is_one_coset"),
    ],
)
def test_last_line(table: str, expected: str) -> None:
    program = vandevelo(table)
    assert program.splitlines()[-1] == expected


def test_an_input_tested_mostly_for_zero_is_read_negated() -> None:
    """``~!>`` on the read replaces every ``== Nil`` test of that input."""
    lines = vandevelo("10000000").splitlines()
    assert lines[:3] == ["a ~!> Inp?", "b ~!> Inp?", "c ~!> Inp?"]
    assert lines[-1] == "c? :: b? :: a? :: loop?"


def test_a_register_binds_the_polarity_its_test_wants() -> None:
    """The last toggle is ``==`` when the clause wants the parity at 0."""
    lines = vandevelo("00001001").splitlines()
    assert lines[4:] == ["d ~> c?", "d ~> d? == b?", "d? :: a? :: loop?"]


def test_a_test_implied_by_an_earlier_half_space_is_dropped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rows past ``a? :: loop?`` all have ``a`` at 0; nothing tests it again."""
    import importlib

    module = importlib.import_module("esolangs.languages.vandevelo.generator")
    monkeypatch.setattr(module, "_affine_coset", lambda *_: None)
    lines = vandevelo("01111111").splitlines()
    assert lines[4:] == ["a? :: loop?", "c? :: loop?", "b? :: loop?"]


def _steps(program: str, bits: tuple[int, ...]) -> int:
    """Steps to the halt, or to the first repeated state of a hanging row."""
    machine = _Machine(program, ScriptedIO("".join(f"{bit}\n" for bit in bits)))
    seen = set()
    steps = 0
    while not machine.halted and machine.snapshot() not in seen:
        seen.add(machine.snapshot())
        machine.step()
        steps += 1
    return steps


def test_three_input_steps_and_sizes() -> None:
    """Negated reads, register polarity and pruning, over all 256 tables."""
    size = steps = 0
    for index in range(256):
        program = vandevelo(format(index, "08b"))
        size += len(program)
        steps += sum(_steps(program, bits) for bits in product(range(2), repeat=3))
    assert (size, steps) == (23425, 23430)


def test_parity_is_a_single_hyperplane() -> None:
    """The parity table's 1-set is one affine coset: one register, one guard."""
    parity = "".join("1" if bin(i).count("1") % 2 else "0" for i in range(2**8))
    lines = vandevelo(parity).splitlines()
    assert lines[-1] == "i? :: loop?"
    # 8 reads, the loop line, 8 register lines building the parity, 1 guard.
    assert len(lines) == 18


def test_affine_tables_bypass_the_peel(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    module = importlib.import_module("esolangs.languages.vandevelo.generator")

    def reject(*_args: object) -> None:
        raise AssertionError("an affine table entered the cube peel")

    monkeypatch.setattr(module, "_Peel", reject)
    for n in range(1, 5):
        for mask in range(1 << n):
            for offset in (0, 1):
                table = "".join(
                    str(((row & mask).bit_count() % 2) ^ offset)
                    for row in range(1 << n)
                )
                program = vandevelo(table)
                for bits in product((0, 1), repeat=n):
                    io = ScriptedIO("\n".join(map(str, bits)))
                    halted = run_until_halt_or_cycle(_Machine(program, io))
                    row = int("".join(map(str, bits)), 2)
                    assert str(int(not halted)) == table[row]
                    assert io.reads == n


@pytest.mark.medium
def test_affine_cosets_and_complements_bypass_the_peel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import importlib

    from esolangs.languages.vandevelo.generator import _affine_coset

    module = importlib.import_module("esolangs.languages.vandevelo.generator")

    def reject(*_args: object) -> None:
        raise AssertionError("an affine coset entered the cube peel")

    monkeypatch.setattr(module, "_Peel", reject)
    for n in range(1, 5):
        for value in range(1 << (1 << n)):
            table = format(value, f"0{1 << n}b")
            ones = {row for row, entry in enumerate(table) if entry == "1"}
            found = _affine_coset(table, ones)
            base = min(ones, default=0)
            closed = bool(ones) and all(
                left ^ right ^ base in ones for left in ones for right in ones
            )
            assert (found is not None) == closed
            if found is None:
                continue
            origin, dirs = found
            points = {origin}
            for direction in dirs:
                assert direction ^ origin not in points
                points |= {point ^ direction for point in points}
            assert points == ones
            complement = "".join("1" if entry == "0" else "0" for entry in table)
            for target in (table, complement):
                program = vandevelo(target)
                for bits in product((0, 1), repeat=n):
                    io = ScriptedIO("\n".join(map(str, bits)))
                    halted = run_until_halt_or_cycle(_Machine(program, io))
                    row = int("".join(map(str, bits)), 2)
                    assert str(int(not halted)) == target[row]
                    assert io.reads == n


def test_coset_membership_work_is_geometric() -> None:
    from esolangs.languages.vandevelo.generator import _affine_coset

    class CountedTable(str):
        reads = 0

        def __getitem__(self, key: int | slice) -> str:
            self.reads += 1
            return super().__getitem__(key)

    for n in range(2, 13):
        ones = {row for row in range(1 << n) if row & 3 == 0}
        table = CountedTable(
            "".join("1" if row in ones else "0" for row in range(1 << n))
        )
        assert _affine_coset(table, ones) is not None
        assert table.reads == len(ones) - 1


def test_the_exact_autocorrelation_improves_on_the_scored_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The fallback that makes the clause bound a bound, not a heuristic."""
    import importlib

    table = "1101010110111010"
    program = vandevelo(table)
    results = (_result(program, bits) for bits in product(range(2), repeat=4))
    assert "".join(results) == table
    module = importlib.import_module("esolangs.languages.vandevelo.generator")
    monkeypatch.setattr(module, "_ensure_popular", lambda *_: None)
    assert len(vandevelo(table)) > len(program)


def test_the_peel_partitions_the_one_set_into_cubes() -> None:
    """Every harvested cube lies in the 1-set, and together they tile it."""
    import random

    from esolangs.languages.vandevelo.generator import _Peel

    rng = random.Random(5)
    for n in (6, 8, 9):
        for density in (0.5, 0.15):
            ones = {i for i in range(1 << n) if rng.random() < density}
            if not ones:
                continue
            seen: set[int] = set()
            for base, dirs in _Peel(set(ones), n).run():
                cube = {base}
                for v in dirs:
                    cube |= {p ^ v for p in cube}
                assert len(cube) == 1 << len(dirs), "dependent directions"
                assert cube <= ones, "a cube left the 1-set"
                assert not cube & seen, "two cubes share a point"
                seen |= cube
            assert seen == ones


def test_registers_are_reused_and_morphed_on_a_wide_table() -> None:
    """Wide tables drive register reuse, morphing, and back-substitution."""
    table = "0011110011110111100001000000010001110110010000001111000111000111"
    program = vandevelo(table)
    lines = program.splitlines()
    morphs = [line for line in lines if "~>" in line and "!=" in line]
    assert morphs, "no register was built or morphed"
    results = (_result(program, bits) for bits in product(range(2), repeat=6))
    assert "".join(results) == table


def _spread_cube(n: int, dim: int) -> list[int]:
    """Directions whose columns run through every nonzero value of F2^dim."""
    return [
        sum(((j % (2**dim - 1) + 1) >> i & 1) << j for j in range(n))
        for i in range(dim)
    ]


def _check_basis(dirs: list[int], n: int) -> list[int]:
    from esolangs.languages.vandevelo.generator import _constraints

    duals = [w for w, _ in _constraints(0, dirs, n)]
    assert len(duals) == n - len(dirs)
    assert all((w & v).bit_count() % 2 == 0 for w in duals for v in dirs)
    # independent: eliminate on leading bits
    rows: dict[int, int] = {}
    for w in duals:
        while w and (w.bit_length() - 1) in rows:
            w ^= rows[w.bit_length() - 1]
        assert w
        rows[w.bit_length() - 1] = w
    return duals


def test_constraints_weigh_four_per_input_plus_a_core() -> None:
    """The O(T) upkeep bound rests on the per-clause constraint weight."""
    from esolangs.languages.vandevelo.generator import _echelon

    n, dim = 16, 4
    dirs = _spread_cube(n, dim)
    duals = _check_basis(dirs, n)
    echelon = sum(w.bit_count() for w in _echelon(dirs, n))
    assert echelon >= n * dim // 2
    core = 1 + 2 ** ((dim + 1) / 2)
    assert sum(w.bit_count() for w in duals) < echelon
    assert sum(w.bit_count() for w in duals) <= 4 * n + (dim + 1) * core
    assert sum(w.bit_count() > 4 for w in duals) <= core - dim


def test_constraints_keep_the_earliest_triple_before_a_later_pair() -> None:
    """A five-column dependency offers both witnesses; the first stays stable."""
    from esolangs.languages.vandevelo.generator import _constraints

    columns = (1, 2, 4, 8, 15, 7)
    dirs = [
        sum(((col >> bit) & 1) << j for j, col in enumerate(columns))
        for bit in range(4)
    ]
    # Column 7 is 1^2^4 before the later 8^15 pair becomes available.
    assert _constraints(0, dirs, 6) == [(0b100111, 0), (0b111000, 0)]
    _check_basis(dirs, 6)


def test_repeated_columns_keep_the_witness_before_core_growth() -> None:
    from esolangs.languages.vandevelo.generator import _constraints

    columns = (1, 2, 4, 7, 8, 15, 7)
    dirs = [
        sum(((col >> bit) & 1) << j for j, col in enumerate(columns))
        for bit in range(4)
    ]
    # Both occurrences of 7 retain 1^2^4 after the later 8^15 pair appears.
    assert _constraints(0, dirs, 7)[:2] == [(0b0001111, 0), (0b1000111, 0)]
    _check_basis(dirs, 7)


def test_constraint_bound_holds_on_random_cubes() -> None:
    import random

    rng = random.Random(3)
    for n in range(2, 14):
        for dim in range(1, n):
            for _ in range(4):
                dirs: list[int] = []
                span = {0}
                while len(dirs) < dim:
                    v = rng.randrange(1, 1 << n)
                    if v not in span:
                        dirs.append(v)
                        span |= {s ^ v for s in span}
                duals = _check_basis(dirs, n)
                core = 1 + 2 ** ((dim + 1) / 2)
                assert sum(w.bit_count() for w in duals) <= 4 * n + (dim + 1) * core
                assert sum(w.bit_count() > 4 for w in duals) <= core - dim


def test_a_full_bank_respells_its_least_recently_used_register(monkeypatch) -> None:
    """The cap that keeps register names as short as input names."""
    import importlib

    module = importlib.import_module("esolangs.languages.vandevelo.generator")
    monkeypatch.setattr(module, "_bank_cap", lambda n: n)
    table = "0011110011110111100001000000010001110110010000001111000111000111"
    program = vandevelo(table)
    lines = program.splitlines()
    registers = {
        line.split(" ~> ")[0] for line in lines if "~>" in line and "Inp" not in line
    }
    assert len(registers) == 6
    assert (
        sum("~>" in line and "!=" not in line and "Inp" not in line for line in lines)
        > 6
    )
    results = (_result(program, bits) for bits in product(range(2), repeat=6))
    assert "".join(results) == table


def test_short_names_are_unique_and_skip_builtins() -> None:
    """The compact namespace does not shadow input, nil, or the loop."""
    from esolangs.languages.vandevelo.generator import _ALPHABET, _RESERVED
    from esolangs.tools.helpers import short_name

    names = [short_name(index, _ALPHABET) for index in range(500)]
    assert len(set(names)) == len(names)
    assert not set(names) & _RESERVED


def test_a_near_full_chain_holds_cosets_not_points() -> None:
    """Three zeros keep each level near ``T``; its stored cosets halve."""
    from esolangs.languages.vandevelo.generator import _Node

    n = 12
    node = _Node.root(set(range(1 << n)) - {5, 1234, 4000})
    for level in range(1, n - 2):
        node = node.below(1 << (level - 1))
        assert node.size >= (1 << n) - (3 << level)
        assert len(node.reps) == node.size >> level
        assert all(
            node.reduce(r) == r == min(r ^ s for s in node.span()) for r in node.reps
        )


# Sampled popular-direction fallback, with a forced positive control.


def test_fallback_draws_a_half_average_direction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Three span cosets with no scored candidate: the fallback must fire."""
    module = importlib.import_module("esolangs.languages.vandevelo.generator")
    span = set(range(4))
    points = {base ^ offset for base in (0, 4, 8) for offset in span}
    node = _Node.root(points).below(1).below(2)
    draws = []

    def counted(node: _Node, v: int) -> int:
        draws.append(v)
        return _pairs(node, v)

    monkeypatch.setattr(module, "_pairs", counted)
    _ensure_popular(node, 6)
    direction, count = _best(node)
    assert direction is not None
    assert direction not in span
    assert count == sum((point ^ direction) in points for point in points) == 8
    assert 2 * count * 64 >= len(points) ** 2
    assert 1 <= len(draws) <= _SAMPLES


def test_assure_finds_a_half_average_direction() -> None:
    """Sparse, dense, and inside a span: the pigeonhole bucket count suffices."""
    import random

    from esolangs.languages.vandevelo.generator import _assure

    rng = random.Random(3)
    n = 8
    for density, span_dirs in ((0.05, []), (0.6, []), (0.97, []), (0.6, [0b1011])):
        points = {p for p in range(1 << n) if rng.random() < density}
        node = _Node.root(points)
        for v in span_dirs:
            node = node.below(v)
        _assure(node, n)
        direction, count = _best(node)
        assert direction is not None
        assert node.reduce(direction)
        assert count == _pairs(node, node.reduce(direction))
        size, span = node.size, 1 << node.dim
        assert 2 * count * ((1 << n) - span) >= size * (size - span)


def test_the_clause_bound_holds_on_assure_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No scored candidates, no sampling: the guarded chains still bound C."""
    import random

    from esolangs.languages.vandevelo.generator import _Peel

    module = importlib.import_module("esolangs.languages.vandevelo.generator")
    monkeypatch.setattr(module, "_nearest", lambda *_, **__: [])
    monkeypatch.setattr(module, "_ensure_popular", lambda *_: None)
    rng = random.Random(7)
    for n in (8, 10):
        ones = {p for p in range(1 << n) if rng.random() < 0.5}
        cubes = _Peel(set(ones), n).run()
        covered: set[int] = set()
        for base, dirs in cubes:
            cube = {base}
            for v in dirs:
                cube |= {p ^ v for p in cube}
            covered |= cube
        assert covered == ones
        assert len(cubes) * n <= 17 << n
        assert len(cubes) * n < 1 << n


def test_certification_refresh_scans_charge_to_removed_cosets(monkeypatch) -> None:
    from esolangs.languages.vandevelo.generator import _Peel

    peel = _Peel(set(range(128)), 7)
    refresh = _Peel.refresh
    charges = []

    def counted(self, node):
        removed = node.removed >> node.dim
        assert len(node.reps) <= 4 * removed
        charges.append((len(node.reps), removed))
        refresh(self, node)

    monkeypatch.setattr(_Peel, "refresh", counted)
    first = peel.certify()
    for _ in range(8):
        assert peel.certify() is first
    assert charges == [], "unchanged certification rescanned a candidate pool"
    for point in range(32):
        peel.take(point)
        peel.certify()
    assert charges, "no refresh crossed the removal threshold"
    assert sum(q for q, _ in charges) <= 4 * sum(r for _, r in charges)


def test_certification_assures_unrefreshed_candidate_pools(monkeypatch) -> None:
    from esolangs.languages.vandevelo.generator import _Peel

    module = importlib.import_module("esolangs.languages.vandevelo.generator")
    monkeypatch.setattr(module, "_nearest", lambda *_, **__: [])
    monkeypatch.setattr(module, "_ensure_popular", lambda *_: None)
    peel = _Peel({row for row in range(256) if row % 5 != 0}, 8)

    def reject(*_args):
        raise AssertionError("an unchanged pool was refreshed")

    monkeypatch.setattr(_Peel, "refresh", reject)
    node = peel.certify()
    assert node is not None
    # Empty candidate pools force the exact fallback at every new level.
    for parent in (peel.root, node):
        while parent.child is not None:
            child = parent.child
            count = _pairs(parent, parent.reduce(child.v))
            size, span = parent.size, 1 << parent.dim
            assert 2 * count * (256 - span) >= size * (size - span)
            parent = child
    assert peel.certify() is node


def test_certification_discards_dead_candidates_before_refresh() -> None:
    from esolangs.languages.vandevelo.generator import _Peel

    peel = _Peel({*range(128), 200, 201}, 8)
    node = peel.certify()
    assert node is not None
    direction = node.reduce(200) ^ min(node.reps)
    node.canon[direction] = direction
    node.cands[direction] = _pairs(node, direction)
    assert node.cands[direction] == 2 << node.dim
    peel.take(200)
    assert node.cands[direction] == 0
    assert node.removed * 4 < node.size
    assert peel.certify() is node
    assert direction not in node.cands
    assert direction not in node.canon
    assert node.removed > 0, "discarding candidates reset the removal charge"


@pytest.mark.medium
def test_identifier_charge_on_a_rendered_wide_program() -> None:
    import random
    import re

    from esolangs.interpreters.io import ScriptedIO
    from esolangs.languages.vandevelo.generator import _ALPHABET, _bank_cap, vandevelo
    from esolangs.languages.vandevelo.interpreter import _Machine
    from esolangs.tools.helpers import short_name
    from esolangs.vm import run_until_halt_or_cycle

    n = 13
    table = f"{random.Random(0).getrandbits(1 << n):0{1 << n}b}"
    program = vandevelo(table)
    identifiers = [
        name
        for name in re.findall(r"[A-Za-z0-9_&*$]+", program)
        if name not in {"Inp", "Nil", "loop"}
    ]
    limit = len(short_name(n + _bank_cap(n) - 1, _ALPHABET))
    assert max(map(len, identifiers)) == 2
    assert max(map(len, identifiers)) <= limit
    assert sum(map(len, identifiers)) > len(identifiers)
    for row in (0, 1, (1 << n) - 1):
        stdin = "".join(f"{bit}\n" for bit in f"{row:0{n}b}")
        machine = _Machine(program, ScriptedIO(stdin))
        actual = "0" if run_until_halt_or_cycle(machine, limit=100_000) else "1"
        assert actual == table[row]


def test_refresh_skips_a_full_pool_and_refills_after_pair_loss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from esolangs.languages.vandevelo.generator import (
        _CANDIDATES,
        _nearest,
        _Peel,
        _remove,
    )

    module = importlib.import_module("esolangs.languages.vandevelo.generator")
    peel = _Peel(set(range(128)), 7)
    calls: list[int] = []

    def counted(node: _Node, pivot: int, seen: set[int], n: int, cap: int) -> list[int]:
        calls.append(cap)
        return _nearest(node, pivot, seen, n, cap)

    monkeypatch.setattr(module, "_nearest", counted)
    assert len(peel.root.cands) == _CANDIDATES
    before = dict(peel.root.cands)
    peel.refresh(peel.root)
    assert calls == []
    assert peel.root.cands == before

    for point in range(1, 128, 2):
        _remove(peel.root, point)
    missing = sum(_pairs(peel.root, v) == 0 for v in before)
    assert 0 < missing < _CANDIDATES
    peel.refresh(peel.root)
    assert calls == [missing]
    assert len(peel.root.cands) == _CANDIDATES
    assert all(
        _pairs(peel.root, v) == count == 64 for v, count in peel.root.cands.items()
    )


@pytest.mark.parametrize("density", [1, 2, 5, 16])
@pytest.mark.parametrize("cap", [0, 1, 3, 12, 48])
def test_nearest_matches_independent_expanded_quotient(density, cap) -> None:
    from esolangs.languages.vandevelo.generator import _nearest, _Node

    n = 6
    node = _Node.root(set(range(1 << n))).below(0b100101).below(0b010011)
    node.reps.intersection_update(sorted(node.reps)[:density])
    span = set(node.span())
    assert len(span) == 4
    assert all(node.reduce(r) == r for r in node.reps)
    points = {r ^ s for r in node.reps for s in span}
    ordered = sorted(range(1, 1 << n), key=lambda v: (v.bit_count(), v))
    for pivot in node.reps:
        for seen in (set(), {0, 1, 2, 3, 8, 13, 21, 37}):
            expected = [
                v
                for v in ordered
                if v not in span and pivot ^ v in points and v not in seen
            ][:cap]
            assert _nearest(node, pivot, seen, n, cap) == expected
            probed = [
                v
                for v in ordered[: 4 * cap]
                if v not in span and pivot ^ v in points and v not in seen
            ][:cap]
            assert _nearest(node, pivot, seen, n, cap, scan=False) == probed


def test_nearest_fallback_reduces_only_the_bounded_probes(monkeypatch) -> None:
    from esolangs.languages.vandevelo.generator import _nearest, _Node

    node = _Node.root(set(range(256))).below(0b10010101).below(0b01001011)
    reduce = _Node.reduce
    calls = []

    def counted_reduce(self, value):
        calls.append(value)
        return reduce(self, value)

    monkeypatch.setattr(_Node, "reduce", counted_reduce)
    # Only one other representative's coset remains; its high-weight
    # differences force the fallback and include equal-weight tie breaks.
    node.reps.intersection_update({0, max(node.reps)})
    result = _nearest(node, 0, {0}, 8, 8)
    assert result == sorted(
        [max(node.reps) ^ s for s in node.span()],
        key=lambda v: (v.bit_count(), v),
    )
    assert len(calls) == 4 * 8


@pytest.mark.medium
def test_nearest_corpus_matches_direct_reduction_and_executes(monkeypatch) -> None:
    import heapq
    import importlib
    import random

    module = importlib.import_module("esolangs.languages.vandevelo.generator")
    rng = random.Random(739)
    tables = [format(i, "08b") for i in range(256)]
    for n in (4, 5, 6):
        for density in (0.1, 0.5, 0.9):
            tables.extend(
                "".join(str(int(rng.random() < density)) for _ in range(1 << n))
                for _ in range(4)
            )
    programs = [(vandevelo(t), vandevelo(t, width=1)) for t in tables]
    from esolangs.languages.vandevelo.generator import _nearest as nearest

    def direct_nearest(node, pivot, seen, n, cap, *, scan=True):
        assert pivot in node.reps
        assert node.reduce(pivot) == pivot
        assert all(node.reduce(r) == r for r in node.reps)
        span = node.span()
        assert all(node.reduce(s) == 0 for s in span)
        out = nearest(node, pivot, seen, n, cap, scan=False)
        if scan and len(out) < cap:
            found = set(out)
            extra = heapq.nsmallest(
                cap - len(out),
                (
                    (v.bit_count(), v)
                    for v in (pivot ^ r ^ s for r in node.reps for s in span)
                    if v and node.reduce(v) and v not in seen and v not in found
                ),
            )
            out.extend(v for _, v in extra)
        return out

    monkeypatch.setattr(module, "_nearest", direct_nearest)
    for table, pair in zip(tables, programs, strict=True):
        assert pair == (vandevelo(table), vandevelo(table, width=1))
        n = len(table).bit_length() - 1
        for program in pair:
            assert (
                "".join(_result(program, bits) for bits in product(range(2), repeat=n))
                == table
            )
