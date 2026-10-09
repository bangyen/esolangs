"""Executed controls for the additional research tracks."""

import itertools
import random
from collections import Counter

import pytest
import sympy

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.fractran import run
from esolangs.interpreters.tape_based.brainfuck import _Machine
from esolangs.tools.b_tapemark import _Builder
from esolangs.tools.brainif import _brainif_dag, _residual_layers
from esolangs.tools.circuit_diagram.hlayout import _LATTICE, _h_size
from tests.proofs._research_dag import read_prune


def test_finite_input_entropy_certificate() -> None:
    alphabet = "><+-.[]"
    matrix = sympy.Matrix(
        [[int(a + b not in {"+-", "-+", "><"}) for b in alphabet] for a in alphabet]
    )
    x = sympy.Symbol("x")
    assert matrix.charpoly(x).as_expr() == sympy.expand(
        x**3 * (x - 1) * (x**3 - 6 * x**2 - 4 * x + 1)
    )
    rate = sympy.Rational(1317, 200)
    vector = sympy.Matrix(
        [(rate - 1) / rate, 1, rate / (rate + 1), rate / (rate + 1), 1, 1, 1]
    )
    assert all(a < rate * b for a, b in zip(matrix * vector, vector, strict=True))
    polynomial = x**3 - 6 * x**2 - 4 * x + 1
    assert polynomial.subs(x, sympy.Rational(65844, 10000)) < 0
    assert polynomial.subs(x, sympy.Rational(65845, 10000)) > 0


def _trace_reads(code: str, bits: tuple[int, ...]) -> tuple[object, set[int]]:
    io = ScriptedIO("".join(chr(bit) for bit in bits))
    machine = _Machine(code, io)
    visited: set[int] = set()
    seen: set[tuple[object, ...]] = set()
    for _ in range(8192):
        if machine.halted:
            return ("halt", io.getvalue()), visited
        state = machine.snapshot()
        if state in seen:
            return ("diverge", ""), visited
        seen.add(state)
        if code[machine.ip] == ",":
            visited.add(machine.ip)
        try:
            machine.step()
        except EOFError:
            return ("EOF", io.getvalue()), visited
    raise AssertionError("trace remained undecided")


@pytest.mark.medium
def test_unvisited_read_pruning_preserves_finite_input_behaviors() -> None:
    inputs = [bits for n in range(3) for bits in itertools.product((0, 1), repeat=n)]
    codes = [
        "".join(commands)
        for length in range(5)
        for commands in itertools.product("><+-.,", repeat=length)
    ]
    codes.extend(["+[>,.<-][,,]", ",[,]", "+[],", "+[[],]", ",[>,.<]"])
    changed = 0
    for code in codes:
        observations = [_trace_reads(code, bits) for bits in inputs]
        visited = set().union(*(places for _, places in observations))
        assert len(visited) <= sum(len(bits) + 1 for bits in inputs)
        normal = read_prune(code, visited)
        changed += normal != code
        assert normal.count(",") <= len(visited)
        assert not any(pair in normal for pair in ("+-", "-+", "><"))
        for bits, (observation, _) in zip(inputs, observations, strict=True):
            assert _trace_reads(normal, bits)[0] == observation
    assert changed > 0
    # A read unreachable on the chosen input can matter outside that domain.
    code = ",[,]"
    _, visited = _trace_reads(code, (0,))
    normal = read_prune(code, visited)
    assert normal == ",[]"
    assert _trace_reads(code, (1,))[0][0] == "EOF"
    assert _trace_reads(normal, (1,))[0][0] == "diverge"


def test_residual_dag_worst_case_width_and_size() -> None:
    for n in range(4, 17):
        r = 0
        while 2 ** (r + 1) + r + 1 <= n:
            r += 1
        width = 2 ** (r + 1)
        table = "".join(format(i, f"0{width}b") for i in range(2**n // width))
        layers = _residual_layers(table)
        assert len(layers[r]) == 2**n // width
        assert 2**n / (2 * n) <= len(layers[r])
        assert sum(map(len, layers)) <= 12 * 2**n / n


def test_h_side_closed_form() -> None:
    for k in range(64):
        assert _h_size(2 * k) == _LATTICE * (12 * 2**k - 4 * k - 10)
        assert _h_size(2 * k + 1) == _LATTICE * (14 * 2**k - 4 * k - 12)
        assert _h_size(2 * k) ** 2 < 144 * _LATTICE**2 * 2 ** (2 * k)
        assert _h_size(2 * k + 1) ** 2 < 144 * _LATTICE**2 * 2 ** (2 * k + 1)


def test_sparse_tapemark_columns_do_not_scan_the_coordinate_span() -> None:
    builder = _Builder()
    assert builder.render() == ""
    builder.put(0, 0, "x")
    builder.put(10**9, 1, "y")
    assert builder.render() == "x\n y"
    assert builder.render(reflect=True) == " y\nx"


@pytest.mark.medium
def test_brainif_selection_size_and_steps_never_regress() -> None:
    from esolangs.interpreters.tape_based.brainif import _Machine as BrainIf
    from esolangs.tools.brainif import _brainif_tree, brainif

    rng = random.Random(20261002)
    old_total = new_total = old_steps = new_steps = 0
    for n in range(1, 7):
        tables = (
            [format(i, f"0{1 << n}b") for i in range(1 << (1 << n))]
            if n <= 3
            else [
                "0" * (1 << n),
                "1" * (1 << n),
                "".join(str(i.bit_count() % 2) for i in range(1 << n)),
                *("".join(rng.choice("01") for _ in range(1 << n)) for _ in range(4)),
            ]
        )
        for table in tables:
            old, new = _brainif_tree(table, None), brainif(table)
            assert len(new) <= len(old)
            counts = []
            for code in (old, new):
                total = 0
                for row in range(1 << n):
                    io = ScriptedIO("".join(format(row, f"0{n}b")))
                    machine = BrainIf(code.splitlines(), io)
                    count = 0
                    while not machine.halted:
                        machine.step()
                        count += 1
                        assert count <= 10000
                    assert io.getvalue() == table[row]
                    assert io.reads == n
                    total += count
                counts.append(total)
            assert counts[1] <= counts[0]
            if n == 3:
                old_total += len(old)
                new_total += len(new)
                old_steps += counts[0]
                new_steps += counts[1]
    assert (old_total, new_total) == (319576, 291524)
    assert (old_steps, new_steps) == (134984, 74440)


@pytest.mark.medium
def test_dag_forgets_the_previous_input_before_reuse() -> None:
    from esolangs.interpreters.tape_based.brainif import _Machine as BrainIf

    code = _brainif_dag("00011011").splitlines()
    for row in range(8):
        io = ScriptedIO("".join(format(row, "03b")))
        machine = BrainIf(code, io)
        boundaries = []
        steps = 0
        while not machine.halted:
            if code[machine.ip] == "if 49 input":
                boundaries.append((machine.ptr, machine.tape))
            machine.step()
            steps += 1
        assert boundaries == [(0, (49,)), (0, (49,))]
        assert steps <= 4 * 3 + 50


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
def test_ordered_reads_retain_four_stores_at_one_cursor() -> None:
    states = []
    for prefix in itertools.product("01", repeat=2):
        io = ScriptedIO("".join((*prefix, "0")))
        machine = _Machine(",>,>,<<.", io)
        while io.reads < 2:
            machine.step()
        states.append(machine.snapshot())
        while not machine.halted:
            machine.step()
        assert io.getvalue() == prefix[0]
    assert len(set(states)) == 4
    assert len({state[0] for state in states}) == 1


@pytest.mark.medium
def test_bounded_input_census_distinguishes_read_observations() -> None:
    inputs = [bits for n in range(3) for bits in itertools.product((0, 1), repeat=n)]
    seen: list[set[tuple[object, ...]]] = [set(), set(), set()]
    for length in range(4):
        for commands in itertools.product("><+-.,", repeat=length):
            behavior = []
            for bits in inputs:
                io = ScriptedIO("".join(chr(bit) for bit in bits))
                machine = _Machine("".join(commands), io)
                try:
                    while not machine.halted:
                        machine.step()
                    behavior.append(("halt", io.getvalue()))
                except EOFError:
                    behavior.append(("EOF",))
            for m in range(3):
                seen[m].add(tuple(behavior[: 2 ** (m + 1) - 1]))
    assert [len(values) for values in seen] == [13, 23, 27]


@pytest.mark.medium
def test_proportional_read_budget_rate() -> None:
    """Rate of Theorem 6's bound when the read budget is `R = p*C`."""
    alphabet = "><+-.[]"
    matrix = sympy.Matrix(
        [[int(a + b not in {"+-", "-+", "><"}) for b in alphabet] for a in alphabet]
    )
    x = sympy.Symbol("x")
    assert matrix.charpoly(x).as_expr() == sympy.expand(
        x**3 * (x - 1) * (x**3 - 6 * x**2 - 4 * x + 1)
    )
    # Exact right Perron vector over Q(lambda), lambda a root of the cubic:
    # A v = lambda v with v_> = (lambda-1)/lambda, v_+ = v_- =
    # (lambda^2 - 5 lambda + 1)/(2 lambda), v_< = v_. = v_[ = v_] = 1.
    lam_sym = sympy.Symbol("lam", positive=True)
    cubic = lam_sym**3 - 6 * lam_sym**2 - 4 * lam_sym + 1
    half = (lam_sym**2 - 5 * lam_sym + 1) / (2 * lam_sym)
    vector = sympy.Matrix([(lam_sym - 1) / lam_sym, 1, half, half, 1, 1, 1])
    for entry in matrix * vector - lam_sym * vector:
        numerator = sympy.together(entry).as_numer_denom()[0]
        assert sympy.rem(sympy.expand(numerator), cubic, lam_sym) == 0
    # v_> is the smallest entry and 1 the largest, so 1^T A^l 1 <=
    # 7 lam^(l+1)/(lam-1), i.e. segments of length l <= K lam^l for the
    # certified K = 7/(lambda-1) <= 7/(6.5844-1) = 1.25349.
    lam_low, lam_high = sympy.Rational(65844, 10000), sympy.Rational(65845, 10000)
    k_high = sympy.Rational(7) / (lam_low - 1)
    assert k_high >= 1  # forced: the empty segment needs K >= 1
    assert 1 + lam_low > sympy.Rational(70347, 10000)  # beats the all-input 7.0347
    # v_> = (lambda-1)/lambda is the smallest entry and 1 the largest.
    assert lam_low**2 - 7 * lam_low + 3 > 0  # a <= c
    assert -(lam_high**2) + 7 * lam_high - 1 > 0  # c <= 1
    cubic_expr = x**3 - 6 * x**2 - 4 * x + 1
    lam: float = float(
        sympy.N(max(sympy.real_roots(cubic_expr), key=lambda r: r.evalf()), 50)
    )
    k: float = 7 / (lam - 1)
    t_star = k / (k + lam)

    def term_rate(t: float) -> float:
        return float(k**t * lam ** (1 - t) / (t**t * (1 - t) ** (1 - t)))

    def rate(p: float) -> float:
        return term_rate(p) if p <= t_star else k + lam

    # Positive control: at p -> 0 the term rate is exactly lambda.
    p_sym = sympy.Symbol("p", positive=True)
    k_sym, lam0 = sympy.symbols("K lambda", positive=True)
    term = (
        k_sym**p_sym * lam0 ** (1 - p_sym) / (p_sym**p_sym * (1 - p_sym) ** (1 - p_sym))
    )
    assert sympy.simplify(term.subs(p_sym, 0) - lam0) == 0
    assert abs(term_rate(1e-8) - lam) < 1e-4

    def direct_root(c: int, p: float) -> float:
        total = sympy.Rational(0)
        for r in range(int(p * c) + 1):
            total += sympy.binomial(c, r) * k_high ** (r + 1) * lam_high ** (c - r)
        return float(float(total) ** (1 / c))

    for p in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9):
        assert rate(p) > lam  # no positive read fraction preserves lambda
        assert abs(direct_root(200, p) - rate(p)) < 0.09
    # Small budgets approach the term rate from below; saturated ones from above.
    assert direct_root(50, 0.1) < direct_root(200, 0.1) < rate(0.1)
    assert rate(0.5) < direct_root(200, 0.5) < direct_root(50, 0.5)
    # The rate is nondecreasing in p, saturating at K + lambda.
    grid = [i / 100 for i in range(1, 101)]
    assert all(rate(a) <= rate(b) + 1e-12 for a, b in itertools.pairwise(grid))
    assert rate(t_star) == pytest.approx(k + lam)
    # Best tested budget is the smallest, and even it exceeds lambda: proportional
    # reads cannot preserve the fixed-set bound.  Since K >= 1, the saturation
    # K + lambda >= 1 + lambda > 7.0347 is worse than the all-input bound too.
    tested = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    assert min(tested, key=rate) == 0.1
    assert rate(0.1) > lam
    assert k + lam > 7.0347 > lam


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
