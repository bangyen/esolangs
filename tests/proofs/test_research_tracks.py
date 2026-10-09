"""Executed controls for the additional research tracks."""

import itertools
import random

import pytest
import sympy

from esolangs.interpreters.io import ScriptedIO
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
