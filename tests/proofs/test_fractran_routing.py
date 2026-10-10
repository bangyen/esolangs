"""Executed controls for FRACTRAN's order-only and pair-decoded routing."""

import itertools
import random
from collections import Counter

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import run


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


@pytest.mark.medium
def test_two_priority_consultations_shatter_a_guard_cycle() -> None:
    # Controls: the four-fraction cycle still tops out at fourteen tables, and
    # the independent pairs still realize all sixteen.
    test_one_priority_consultation_cannot_shatter_a_guard_cycle()
    test_fraction_order_encodes_four_independent_answers()

    from esolangs.interpreters.other.fractran import _Machine

    # Round one consumes phase 13 and one feature and produces 17; the run
    # then consults the same priority list again and round two consumes 17 and
    # a remaining feature.  This escapes the one-consultation linear
    # dependence because the second selection sees a changed feature set.
    router = ("17/39", "17/65", "17/91", "17/143", "2/51", "2/85", "1/187")
    first = set(router[:4])  # 17/(13*f) consumes 13 and f
    second = set(router[4:])  # (1 or 2)/(17*f) consumes 17 and f
    cleanup = ("1/3", "1/5", "1/7", "1/11", "1/17")
    # Table-independent seeds: features (3,11), (3,7,11), (5,7,11), (5,11).
    seeds = (13 * 3 * 11, 13 * 3 * 7 * 11, 13 * 5 * 7 * 11, 13 * 5 * 11)

    observed = set()
    for order in itertools.permutations(router):
        assert Counter(order) == Counter(router)
        answers = []
        for seed in seeds:
            tokens = [str(seed), *order, *cleanup]
            io = ScriptedIO("")
            run(" ".join(tokens), io)
            answer = io.getvalue().strip()
            assert answer in {"1", "2"}
            answers.append(str(int(answer) - 1))
            # Every run selects exactly one round-one and one round-two rule.
            io = ScriptedIO("")
            machine = _Machine(" ".join(tokens), io)
            offset_token = dict(zip(machine.offsets, tokens, strict=True))
            fired = []
            while not machine.halted:
                offset = machine.ip
                if offset is not None:
                    fired.append(offset_token[offset])
                machine.step()
            assert sum(fraction in first for fraction in fired) == 1
            assert sum(fraction in second for fraction in fired) == 1
        observed.add("".join(answers))
    assert observed == {format(i, "04b") for i in range(16)}


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


@pytest.mark.medium
def test_pair_decoded_router_reaches_one_row_per_fraction() -> None:
    # Five features give ten pair rows and ten router fractions; a decoder
    # found by exhaustive search over the pair labels realizes 1024/1024.
    # A sample of orderings is executed to pin the program's final value to
    # A_f*B_g; the remaining tables are then pure enumeration of that map.
    features = (3, 5, 7, 11, 19)
    round1, round2, cleanup = _pair_router(features)
    a = {3: 37, 5: 41, 7: 43, 11: 47, 19: 53}
    b = {3: 61, 5: 67, 7: 71, 11: 73, 19: 79}
    rows = list(itertools.combinations(features, 2))
    rank = {f: i for i, f in enumerate(features)}
    ones = {
        (0, 0),
        (0, 3),
        (1, 0),
        (1, 2),
        (1, 3),
        (1, 4),
        (2, 0),
        (2, 1),
        (2, 3),
        (2, 4),
        (3, 1),
        (3, 2),
        (3, 4),
        (4, 0),
        (4, 1),
        (4, 2),
        (4, 3),
    }
    orders = list(itertools.permutations(features))
    rng = random.Random(20261004)
    for _ in range(200):
        order1, order2 = rng.choice(orders), rng.choice(orders)
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
    tables = set()
    for order1 in orders:
        for order2 in orders:
            labels = []
            for x, y in rows:
                first = min((x, y), key=order1.index)
                second = min((x, y), key=order2.index)
                labels.append("1" if (rank[first], rank[second]) in ones else "0")
            tables.add("".join(labels))
    assert tables == {format(i, "010b") for i in range(1024)}


@pytest.mark.medium
def test_pair_decoded_router_shatters_thirteen_rows_at_six_features() -> None:
    # Six features, the 13 pair rows left after deleting two disjoint pairs:
    # an annealed decoder realizes 8192/8192, past d=12 fractions.  Every edge
    # row's (first, second) lies in its own pair, so disjoint copies give
    # 13*floor(k/6) rows; the region count caps pair rows at 9.33*(k-1).
    features = (3, 5, 7, 11, 19, 23)
    round1, round2, cleanup = _pair_router(features)
    a = dict(zip(features, (37, 41, 43, 47, 53, 59), strict=True))
    b = dict(zip(features, (61, 67, 71, 73, 79, 83), strict=True))
    dropped = {(0, 1), (4, 5)}
    rows = [p for p in itertools.combinations(range(6), 2) if p not in dropped]
    decoder = ("110000", "100010", "011000", "010100", "000011", "010011")
    orders = list(itertools.permutations(range(6)))
    rng = random.Random(20261007)
    for _ in range(40):
        order1, order2 = rng.choice(orders), rng.choice(orders)
        for x, y in rows:
            fx, fy = features[x], features[y]
            tokens = [
                str(13 * fx * fx * fy * fy),
                *(round1[features[f]] for f in order1),
                *(round2[features[g]] for g in order2),
                *cleanup,
            ]
            io = ScriptedIO("")
            run(" ".join(tokens), io)
            first = features[min((x, y), key=order1.index)]
            second = features[min((x, y), key=order2.index)]
            assert int(io.getvalue().strip()) == a[first] * b[second]
    choices = {tuple(min(row, key=order.index) for row in rows) for order in orders}
    assert len(choices) == 504  # acyclic orientations of the 13-edge graph
    tables = {
        "".join(decoder[p][q] for p, q in zip(c1, c2, strict=True))
        for c1 in choices
        for c2 in choices
    }
    assert len(tables) == 2**13


@pytest.mark.medium
def test_pair_router_dense_complements_have_a_prefix_obstruction() -> None:
    # Omitting two features exposes only the first three in each order:
    # 120 selection vectors cap every decoder below 2**15 tables.
    features = (3, 5, 7, 11, 19, 23)
    round1, round2, cleanup = _pair_router(features)
    a = dict(zip(features, (37, 41, 43, 47, 53, 59), strict=True))
    b = dict(zip(features, (61, 67, 71, 73, 79, 83), strict=True))
    pairs = list(itertools.combinations(range(6), 2))
    rows = [tuple(i for i in range(6) if i not in pair) for pair in pairs]
    orders = list(itertools.permutations(range(6)))
    choices = {tuple(min(row, key=order.index) for row in rows) for order in orders}
    prefixes = {
        tuple(next(i for i in prefix if i in row) for row in rows)
        for prefix in itertools.permutations(range(6), 3)
    }
    assert choices == prefixes
    assert len(choices) == 120
    assert len(choices) ** 2 < 2 ** len(rows)
    rng = random.Random(20261007)
    for _ in range(40):
        order1, order2 = rng.choice(orders), rng.choice(orders)
        for row in rows:
            seed = 13
            for i in row:
                seed *= features[i] ** 2
            tokens = [
                str(seed),
                *(round1[features[f]] for f in order1),
                *(round2[features[g]] for g in order2),
                *cleanup,
            ]
            io = ScriptedIO("")
            run(" ".join(tokens), io)
            first = features[min(row, key=order1.index)]
            second = features[min(row, key=order2.index)]
            assert int(io.getvalue().strip()) == a[first] * b[second]
    decoder = ("110000", "100010", "011000", "010100", "000011", "010011")
    tables = {
        "".join(decoder[p][q] for p, q in zip(c1, c2, strict=True))
        for c1 in choices
        for c2 in choices
    }
    assert len(tables) == 845
    # The same decoder's known pair-row family is the positive control.
    control = [pair for pair in pairs if pair not in {(0, 1), (4, 5)}]
    control_choices = {
        tuple(min(row, key=order.index) for row in control) for order in orders
    }
    control_tables = {
        "".join(decoder[p][q] for p, q in zip(c1, c2, strict=True))
        for c1 in control_choices
        for c2 in control_choices
    }
    assert len(control_tables) == 8192


@pytest.mark.medium
def test_pair_router_is_a_quadratic_sign_family() -> None:
    # Base four makes the selected product dominate all remaining products,
    # for every decoder. Warren then bounds arbitrary row sizes by O(k).
    features = (3, 5, 7, 11)
    round1, round2, cleanup = _pair_router(features)
    a = dict(zip(features, (37, 41, 43, 47), strict=True))
    b = dict(zip(features, (61, 67, 71, 73), strict=True))
    rows = [
        row for size in range(1, 5) for row in itertools.combinations(range(4), size)
    ]
    tables = set()
    orders = list(itertools.permutations(range(4)))
    for order1 in orders:
        u = {f: 4 ** (3 - i) for i, f in enumerate(order1)}
        for order2 in orders:
            v = {f: 4 ** (3 - i) for i, f in enumerate(order2)}
            pair_labels = []
            for row in rows:
                first = min(row, key=order1.index)
                second = min(row, key=order2.index)
                selected = u[first] * v[second]
                remainder = sum(u[i] for i in row) * sum(v[j] for j in row)
                remainder -= selected
                assert selected > remainder
                assert 9 * remainder < 7 * selected
                value = sum(
                    (1 if i == j and i != 3 else -1) * u[i] * v[j]
                    for i in row
                    for j in row
                )
                seed = 13
                for i in row:
                    seed *= features[i] ** 2
                tokens = [
                    str(seed),
                    *(round1[features[f]] for f in order1),
                    *(round2[features[g]] for g in order2),
                    *cleanup,
                ]
                io = ScriptedIO("")
                run(" ".join(tokens), io)
                result = int(io.getvalue().strip())
                assert result == a[features[first]] * b[features[second]]
                label = first == second and first != 3
                assert value != 0
                assert (value > 0) == label
                if len(row) == 2:
                    pair_labels.append("1" if label else "0")
            tables.add("".join(pair_labels))
    assert len(tables) == 64  # known shattering family, positive control
    # At T=16k, Warren's base is 64e < 192 < 2**8; above this,
    # 2**c/c increases for c=T/(2k)>=8, so shattering stays impossible.
    assert 64 * 3 < 2**8
