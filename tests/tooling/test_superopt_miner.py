"""The stochastic miner's operators, scoring, caps and records.

The chain itself is exercised at toy budgets only: rediscovery
rates are the control gate's question (a run-phase run), never a
unit test's.  One planted-gap recovery is pinned, per the plan:
the sampler must be able to walk from a padded seed back to the
known FALSE gap program's size.
"""

import json
import random
import sys
from itertools import pairwise
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from superopt.audit import Runner, corpus_for
from superopt.mine import (
    CONTROL_CAP_CPU_S,
    OPERATORS,
    SCREEN_ROW_TIMEOUT,
    TOTAL_CAP_CPU_S,
    Ledger,
    Score,
    _decode_rng,
    _encode_rng,
    class_table,
    hunt_tables,
    mine_search,
    named_tables,
    painfuck_admissible,
    painfuck_decoded,
    propose,
    review_required,
    score_program,
    temperature,
)

from esolangs.exceptions import ExecutionTimeoutError

ALPHABET = tuple("ab^%01.")
SEED_PROGRAM = "^%01.ab"


def _rng() -> random.Random:
    return random.Random(184_700)


def test_operator_weights_are_the_plans() -> None:
    """The operator set and weights are plan section 3's table, verbatim."""
    assert [name for name, _w, _f in OPERATORS] == [
        "substitute",
        "delete_char",
        "insert",
        "delete_span",
        "move_span",
        "duplicate_span",
        "replace_span",
    ]
    assert sum(weight for _n, weight, _f in OPERATORS) == 1.0


def test_operators_stay_in_the_alphabet() -> None:
    """Every operator's output is a string over the corpus alphabet,
    on long, short and empty programs alike."""
    rng = _rng()
    for program in (SEED_PROGRAM, "a", ""):
        for _name, _weight, operator in OPERATORS:
            for _ in range(50):
                out = operator(program, ALPHABET, rng)
                assert set(out) <= set(ALPHABET), (operator, program, out)


def test_operator_shapes() -> None:
    """Length effects: substitute/move preserve, delete shrinks,
    insert/duplicate grow, replace stays within its span budget."""
    rng = _rng()
    by_name = {name: op for name, _w, op in OPERATORS}
    for _ in range(100):
        assert len(by_name["substitute"](SEED_PROGRAM, ALPHABET, rng)) == len(
            SEED_PROGRAM
        )
        assert (
            len(by_name["delete_char"](SEED_PROGRAM, ALPHABET, rng))
            == len(SEED_PROGRAM) - 1
        )
        assert (
            len(by_name["insert"](SEED_PROGRAM, ALPHABET, rng)) == len(SEED_PROGRAM) + 1
        )
        moved = by_name["move_span"](SEED_PROGRAM, ALPHABET, rng)
        assert sorted(moved) == sorted(SEED_PROGRAM)
        shrunk = by_name["delete_span"](SEED_PROGRAM, ALPHABET, rng)
        assert len(SEED_PROGRAM) - 8 <= len(shrunk) < len(SEED_PROGRAM)
        grown = by_name["duplicate_span"](SEED_PROGRAM, ALPHABET, rng)
        assert len(SEED_PROGRAM) < len(grown) <= len(SEED_PROGRAM) + 8
        swapped = by_name["replace_span"](SEED_PROGRAM, ALPHABET, rng)
        assert len(SEED_PROGRAM) - 4 <= len(swapped) <= len(SEED_PROGRAM) + 3


def test_propose_uses_the_weighted_set() -> None:
    """Proposals are reproducible under a fixed seed and in-alphabet."""
    first = [propose(SEED_PROGRAM, ALPHABET, _rng()) for _ in range(5)]
    second = [propose(SEED_PROGRAM, ALPHABET, _rng()) for _ in range(5)]
    assert first == second
    assert all(set(out) <= set(ALPHABET) for out in first)


def test_temperature_anneals_geometrically() -> None:
    """Endpoints are the plan's 6.0 -> 0.15, decreasing throughout."""
    steps = 1000
    assert temperature(0, steps) == 6.0
    assert abs(temperature(steps - 1, steps) - 0.15) < 1e-12
    curve = [temperature(step, steps) for step in range(0, steps, 100)]
    assert all(a > b for a, b in pairwise(curve))


def test_cost_formula() -> None:
    """Cost is length + 64 per wrong row + 4096 per timeout row."""
    assert Score(0, 0).cost(7) == 7
    assert Score(2, 0).cost(7) == 7 + 128
    assert Score(0, 1).cost(7) == 7 + 4096
    assert Score(1, 1).cost(0) == 64 + 4096
    assert Score(0, 0).correct
    assert not Score(1, 0).correct
    assert not Score(0, 1).correct


class _StubRunner:
    """A printing-runner stand-in: row 0 times out, row 1 errors."""

    name = "Stub"
    terminating = False

    def answer_row(self, program, bits, *, timeout, backstop):  # noqa: ARG002
        if bits == [0]:
            raise ExecutionTimeoutError("row ran out of bound")
        raise ValueError("interpreter rejected the candidate")


def test_score_counts_timeout_and_wrong_rows() -> None:
    """Screen scoring separates timeout rows from wrong rows and
    never early-exits: both rows of the table are charged."""
    scored = score_program(_StubRunner(), "anything", "00")  # type: ignore[arg-type]
    assert scored == Score(wrong=1, timeouts=1)
    assert scored.cost(3) == 3 + 64 + 4096


def test_score_false_shipped_and_wrong() -> None:
    """Against the real FALSE runner: the shipped program scores
    clean on its table, and a constant-wrong program is charged
    for every row (the audit's early exit would stop at one)."""
    runner = Runner("FALSE")
    assert score_program(runner, "^%1.", "11") == Score(0, 0)
    assert score_program(runner, "0.", "11") == Score(2, 0)
    assert score_program(runner, "0.^", "00") == Score(0, 0)


def test_screen_bound_is_the_plans() -> None:
    """The screen tier's row bound is 50 ms, in code."""
    assert SCREEN_ROW_TIMEOUT == 0.05


def test_painfuck_admissibility() -> None:
    """A candidate decoding to the random ``y`` command is
    inadmissible; the recorded gap program ``ok`` decodes clean."""
    assert painfuck_decoded("y") == "y"
    assert not painfuck_admissible("y")
    assert painfuck_admissible("ok")


def test_rng_state_roundtrip() -> None:
    """Checkpoint encoding restores a chain's RNG exactly."""
    rng = random.Random(99)
    [rng.random() for _ in range(10)]
    clone = _decode_rng(_encode_rng(rng))
    assert [clone.random() for _ in range(5)] == [rng.random() for _ in range(5)]


def test_ledger_accounting_and_caps(tmp_path: Path) -> None:
    """Charges persist across reloads, filter by phase/language,
    and the caps are the plan's 20 / 2 CPU-hours."""
    path = tmp_path / "ledger.json"
    ledger = Ledger(path)
    ledger.charge(
        phase="hunt", language="Painfuck", cpu_s=100.0, evals=10, command="mine-hunt"
    )
    ledger.charge(
        phase="control", language="FALSE", cpu_s=50.0, evals=5, command="mine-control"
    )
    reloaded = Ledger(path)
    assert reloaded.total() == 150.0
    assert reloaded.total(phase="control") == 50.0
    assert reloaded.total(language="Painfuck") == 100.0
    assert reloaded.remaining_total() == TOTAL_CAP_CPU_S - 150.0
    assert reloaded.remaining_control() == CONTROL_CAP_CPU_S - 50.0
    assert TOTAL_CAP_CPU_S == 20 * 3600
    assert CONTROL_CAP_CPU_S == 2 * 3600


def test_review_gate(tmp_path: Path) -> None:
    """A second hunt language waits on the review; the first doesn't."""
    ledger = Ledger(tmp_path / "ledger.json")
    assert not review_required(ledger, "Painfuck")
    ledger.charge(
        phase="hunt", language="Painfuck", cpu_s=1.0, evals=1, command="mine-hunt"
    )
    assert not review_required(ledger, "Painfuck")
    assert review_required(ledger, "FALSE")
    assert review_required(ledger, "Boolfuck")


def test_hunt_table_set_shape() -> None:
    """The hunt set per arity is the plan's: corpus keys, the named
    family, and 12 seeded random tables (22-24 tables)."""
    for n, expected in ((2, 22), (3, 24), (4, 24)):
        items = hunt_tables(n)
        assert len(items) == expected
        labels = [label for label, _table in items]
        assert labels.count("random") == 12
        assert "named/parity" in labels
        assert all(len(table) == 1 << n for _label, table in items)
    assert named_tables(2)["parity"] == "0110"
    by_label = dict(hunt_tables(3))
    assert class_table(3, "tiled") == by_label["tiled"]
    assert class_table(2, "named/and") == named_tables(2)["and"]


def test_mine_search_record_shape(tmp_path: Path) -> None:
    """A toy-budget search returns the plan's record, JSON-clean,
    inside its evaluation budget."""
    runner = Runner("FALSE")
    corpus = corpus_for("FALSE")
    record = mine_search(
        runner,
        corpus.alphabet,
        "00",
        class_label="control",
        phase="control",
        eval_budget=120,
        restarts=1,
        seed=7,
        finds_path=tmp_path / "finds.jsonl",
        rejects_path=tmp_path / "rejects.jsonl",
    )
    for key in (
        "language",
        "arity",
        "table",
        "class",
        "shipped_size",
        "found_size",
        "found",
        "gap_pct",
        "consumption",
        "evals",
        "restarts",
        "seed",
        "wall_s",
    ):
        assert key in record, key
    json.dumps(record)  # the record must stream to JSONL as-is
    assert record["shipped_size"] == 3
    assert record["consumption"] == "verified"
    assert record["outcome"] in ("find", "no_find")
    assert 0 < record["evals"] <= 120
    if record["outcome"] == "find":
        lines = (tmp_path / "finds.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 1
        streamed = json.loads(lines[0])
        assert streamed["found"] == record["found"]
        assert streamed["found_size"] == record["found_size"]


def test_mine_search_recovers_a_planted_gap() -> None:
    """Positive control for the tool itself (plan section 9): FALSE's
    recorded gap ``'0^=.`` on table 10, padded with a no-op pair, must
    be recovered to size <= 5 by a chain seeded from the padded
    program. (Table 10 is the live FALSE gap on current main: the
    generator ships 16 chars there. The original table-00 plant is
    dead -- main now ships the recorded find ``0.^`` itself.)"""
    runner = Runner("FALSE")
    corpus = corpus_for("FALSE")
    record = mine_search(
        runner,
        corpus.alphabet,
        "10",
        class_label="control",
        phase="control",
        eval_budget=4000,
        restarts=1,
        seed=184_700,
        start_program="'0^=.[]",
    )
    assert record["outcome"] == "find"
    assert record["found_size"] is not None
    assert record["found_size"] <= 5
