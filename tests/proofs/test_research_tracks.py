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
from esolangs.tools.circuit_diagram import _LATTICE, _h_size
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


@pytest.mark.medium
def test_forgetting_dag_executes_every_small_table() -> None:
    from esolangs.interpreters.tape_based.brainif import run as run_brainif

    for n in range(1, 4):
        for value in range(1 << (1 << n)):
            table = format(value, f"0{1 << n}b")
            code = _brainif_dag(table)
            for row in range(1 << n):
                io = ScriptedIO("".join(format(row, f"0{n}b")))
                run_brainif(code.splitlines(), io)
                assert io.getvalue() == table[row]
                assert io.reads == n


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
    assert (old_total, new_total) == (319576, 292492)
    assert (old_steps, new_steps) == (134984, 74752)


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
