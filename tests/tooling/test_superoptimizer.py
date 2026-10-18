"""The superoptimizer's model, control and engines, pinned to the repo."""

import sys
from itertools import product
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from superopt.audit import Runner, audit_language, corpus_for, space_below
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


# --- v2: the small-end audit -------------------------------------------


def test_audit_runner_reproduces_shipped_false() -> None:
    """The audit runner executes through the repo's own public API; the
    shipped FALSE programs must certify against their tables."""
    import esolangs

    runner = Runner("FALSE")
    lang = esolangs.Language("FALSE")
    for table in ("00", "01", "10", "11"):
        shipped = lang.generate(table)
        assert runner.certify(shipped, table)
        correct, rows = runner.check(shipped, table)
        assert correct
        assert rows == 2


def test_audit_consumption_oracle() -> None:
    """A program that computes a constant without reading is not a gap:
    the shipped program reads its input once per row, ``1.`` never."""
    runner = Runner("FALSE")
    assert runner.reads("^%1.", "11") == (1, 1)
    assert runner.reads("1.", "11") == (0, 0)
    correct, _ = runner.check("1.", "11")
    assert correct  # correctness alone would call this a gap


def test_audit_space_accounting() -> None:
    """Candidate counts below a size are exact geometric sums."""
    assert space_below(16, 4) == 1 + 16 + 256 + 4096
    assert space_below(1, 9) == 9
    assert space_below(0, 9) == 1
    assert space_below(3, 0) == 0


def test_audit_false_corpus() -> None:
    """The corpus alphabet covers every char the generator emits at
    small arity, and the n=1 sizes are the measured shipped sizes."""
    corpus = corpus_for("FALSE")
    assert corpus.sizes[1] == {"00": 4, "01": 4, "10": 6, "11": 4}
    assert set("^%01.&=[]_'?:;a$") <= set(corpus.alphabet)


@pytest.mark.medium  # ~8k interpreter executions through the public API
def test_audit_pilot_certificates() -> None:
    """The FALSE pilot (RESULTS.md, v2): ``01`` is certified minimal at
    4 and the two constant tables have the recorded 1-char gaps.  The
    budget here still covers each of those outcomes; the n=1 NOT space
    (1.1M strings) is over 20x this cap, so that pair must price out,
    never certify."""
    _, outcomes = audit_language("FALSE", 1, candidate_cap=20_000, wall_seconds=60)
    by_table = {o.table: o for o in outcomes}
    assert by_table["01"].outcome == "certified"
    assert by_table["00"].outcome == "gap"
    assert by_table["00"].found == "0.^"
    assert by_table["11"].outcome == "gap"
    assert by_table["11"].found == "1.^"
    assert by_table["10"].outcome == "priced_out"
