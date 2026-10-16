"""Executed controls for FRACTRAN's order-only and pair-decoded routing."""

import itertools
from collections import Counter

import pytest

from esolangs.languages.fractran.interpreter import run
from esolangs.runtime.io import ScriptedIO


@pytest.mark.medium
def test_fraction_order_encodes_four_independent_answers() -> None:
    primes = (3, 5, 7, 11)
    vocabulary = Counter(f"{answer}/{p}" for p in primes for answer in (1, 2))
    for table in itertools.product("01", repeat=4):
        fractions = []
        for p, bit in zip(primes, table, strict=True):
            pair = [f"1/{p}", f"2/{p}"]
            fractions.extend(pair if bit == "0" else pair[::-1])
        assert Counter(fractions) == vocabulary
        for p, bit in zip(primes, table, strict=True):
            io = ScriptedIO("")
            run(str(p) + " " + " ".join(fractions), io)
            assert io.getvalue().strip() == str(1 + int(bit))
    # Neither rule is applicable outside the selected row vocabulary.
    io = ScriptedIO("")
    run("13 " + " ".join(fractions), io)
    assert io.getvalue().strip() == "13"


@pytest.mark.medium
def test_one_priority_consultation_cannot_shatter_a_guard_cycle() -> None:
    # Positive rules use 3/5; negative rules use 7/11. Consuming phase 13
    # prevents a second priority consultation; fixed cleanup leaves 1 or 2.
    fractions = ("34/39", "34/65", "17/91", "17/143")
    seeds = (13 * 3 * 7, 13 * 3 * 11, 13 * 5 * 7, 13 * 5 * 11)
    observed = set()
    for order in itertools.permutations(fractions):
        assert Counter(order) == Counter(fractions)
        answers = []
        for seed in seeds:
            io = ScriptedIO("")
            run(
                " ".join([str(seed), *order, "1/3", "1/5", "1/7", "1/11", "1/17"]),
                io,
            )
            answer = io.getvalue().strip()
            assert answer in {"1", "2"}
            answers.append(str(int(answer) - 1))
        observed.add("".join(answers))
    assert observed == {format(i, "04b") for i in range(16)} - {"0110", "1001"}


def _pair_router(
    features: tuple[int, ...],
) -> tuple[dict[int, str], dict[int, str], list[str]]:
    """Round-one and round-two marker fractions for the pair-decoded router."""
    phase, marker = 13, 17
    a_mark = (37, 41, 43, 47, 53, 59)
    b_mark = (61, 67, 71, 73, 79, 83)
    a = dict(zip(features, a_mark[: len(features)], strict=True))
    b = dict(zip(features, b_mark[: len(features)], strict=True))
    round1 = {f: f"{marker * a[f]}/{phase * f}" for f in features}
    round2 = {g: f"{b[g]}/{marker * g}" for g in features}
    cleanup = [*(f"1/{f}" for f in features), f"1/{marker}"]
    return round1, round2, cleanup


@pytest.mark.medium
def test_pair_decoded_router_reads_both_selections() -> None:
    # Round one consumes phase 13 and a feature f, emitting marker 17*A_f;
    # round two consumes 17 and a feature g, emitting B_g.  Squared features in
    # the seed let round two reselect the round-one feature, so the final value
    # A_f*B_g depends on both selections.  A fixed decoder on that pair then
    # realizes all 2^T tables: 64/64 at four features and six pair rows.
    features = (3, 5, 7, 11)
    round1, round2, cleanup = _pair_router(features)
    a = {3: 37, 5: 41, 7: 43, 11: 47}
    b = {3: 61, 5: 67, 7: 71, 11: 73}
    rows = list(itertools.combinations(features, 2))
    tables = set()
    for order1 in itertools.permutations(features):
        for order2 in itertools.permutations(features):
            labels = []
            for x, y in rows:
                seed = 13 * x * x * y * y
                tokens = [
                    str(seed),
                    *(round1[f] for f in order1),
                    *(round2[g] for g in order2),
                    *cleanup,
                ]
                io = ScriptedIO("")
                run(" ".join(tokens), io)
                first = min((x, y), key=order1.index)
                second = min((x, y), key=order2.index)
                assert int(io.getvalue().strip()) == a[first] * b[second]
                labels.append("1" if first == second and first != 11 else "0")
            tables.add("".join(labels))
    assert tables == {format(i, "06b") for i in range(64)}
