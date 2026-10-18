"""The superoptimizer's model, control and engines, pinned to the repo."""

import sys
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from superopt.machine import CRAZY0, FULL_ALPHABET, SUFFIX_ALPHABET, run
from superopt.search import Stats, certify, evaluate, order_rows, search, search_bfs
from superopt.targets import (
    INPUTS,
    PREFIX,
    SHIPPED_GADGET,
    SHIPPED_SUFFIX,
    full_spec,
    suffix_spec,
)

from esolangs.languages.malbolge.generator.digits import _GADGET
from esolangs.languages.malbolge.interpreter import _crazy


def test_crazy0_matches_the_interpreter() -> None:
    """The machine's trit table is the interpreter's ``_crazy`` at trit 0."""
    for a in range(3):
        for c in range(3):
            assert CRAZY0[a][c] == _crazy(a, c) % 3


def test_target_constants_match_the_shipped_gadget() -> None:
    """The tool's prefix/suffix constants are digits.py's ``_GADGET``."""
    assert (*PREFIX, *SHIPPED_SUFFIX) == _GADGET
    assert SHIPPED_GADGET == _GADGET


def test_machine_reproduces_the_gadgets_closed_form() -> None:
    """``run`` of the shipped gadget lands on the documented (u, v)."""
    for bits in INPUTS:
        x, y, z = bits
        _, cells = run(SHIPPED_GADGET, bits)
        u = (1 + x - y - x * y * z) % 3
        v = ((2 - x) * (1 - z) + z * x * y) % 3
        assert cells[1:] == (u, v), bits


def test_control_rediscovers_the_unique_shortest_suffix() -> None:
    """Positive control: nothing injective below 6 ops; at 6, only the
    shipped suffix -- the repo's own claim, re-derived by this engine."""
    stats = Stats()
    result = search(suffix_spec(), SUFFIX_ALPHABET, 6, stats)
    assert result.length == 6
    assert result.hits == (SHIPPED_SUFFIX,)
    assert certify(SHIPPED_SUFFIX, suffix_spec())


def test_certify_rejects_wrong_programs() -> None:
    """Certification is exact: plausible-looking programs fail it."""
    assert not certify(SHIPPED_SUFFIX, full_spec())
    assert not certify((*SHIPPED_SUFFIX[:-1], "1"), suffix_spec())
    assert certify(SHIPPED_GADGET, full_spec())


def test_early_exit_filter_agrees_with_certification() -> None:
    """The ordered early-exit filter and the wholesale certifier never
    disagree, and the filter really does stop early on bad candidates."""
    spec = suffix_spec()
    stats = Stats()
    assert not evaluate((), spec, stats)
    assert stats.rows_evaluated < len(INPUTS)
    programs = [
        tuple(p) for length in range(3) for p in product(SUFFIX_ALPHABET, repeat=length)
    ]
    programs.append(SHIPPED_SUFFIX)
    for program in programs:
        assert evaluate(program, spec) == certify(program, spec), program


def test_row_order_is_a_permutation() -> None:
    """Discriminating-power order still visits every row exactly once."""
    assert sorted(order_rows(suffix_spec())) == list(range(len(INPUTS)))


def test_bfs_agrees_with_the_depth_first_search() -> None:
    """The packed breadth-first engine finds the same unique suffix,
    and reports a bounded negative on the full spec at shallow depth."""
    result = search_bfs(suffix_spec(), SUFFIX_ALPHABET, 6)
    assert result.program == SHIPPED_SUFFIX
    shallow = search_bfs(full_spec(), FULL_ALPHABET, 3)
    assert shallow.program is None
    assert shallow.exhausted == 3
    assert not shallow.capped
