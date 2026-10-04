"""Independent graph, bundle and event semantics against executed programs."""

# ruff: noqa: SLF001 -- Compare complete native state against independent semantics.

import itertools
from datetime import UTC, datetime, timedelta

import pytest

from esolangs.interpreters.grid_based import circuit_diagram as native
from esolangs.tools.circuit_diagram import circuit_diagram
from tests.interpreters.circuit_diagram_observer import Factory
from tests.interpreters.test_circuit_diagram import (
    CONSTANT,
    FLIP_FLOP,
    PRIME_TESTER,
    PRIME_TESTER_AS_DRAWN,
)


def inputs(width):
    return map("".join, itertools.product("01", repeat=width))


@pytest.mark.parametrize("n", [1, 2, pytest.param(3, marks=pytest.mark.medium)])
@pytest.mark.parametrize("width", [None, 1, 13, 100])
def test_all_small_generated_tables(n, width):
    for outputs in itertools.product("01", repeat=1 << n):
        table = "".join(outputs)
        factory = Factory(circuit_diagram(table, width).splitlines(), native._Machine)
        for bits in inputs(n):
            assert factory.check(bits, table[int(bits, 2)])["halted"]


@pytest.mark.parametrize("kind", tuple("aAoOxX"))
@pytest.mark.parametrize("width", range(1, 5))
def test_bundle_logic(kind, width):
    code = [f"-{width}-.", f"    {kind}.-:", f"-{width}-."]
    factory = Factory(code, native._Machine)
    for bits in inputs(2 * width):
        count = bits.count("1")
        predicate = {"a": count == len(bits), "o": count > 0, "x": count == 1}[
            kind.lower()
        ]
        expected = predicate if kind.islower() else not predicate
        assert factory.check(bits, str(int(expected)))["halted"]


@pytest.mark.parametrize("width", range(1, 9))
def test_bundle_not_and_sources(width):
    factory = Factory([f"-{width}-~-:"], native._Machine)
    for bits in inputs(width):
        factory.check(bits, "".join(str(1 - int(bit)) for bit in bits))
    for kind, bit in (("(", "0"), (")", "1")):
        Factory([f"{kind}-{width}-:"], native._Machine).check("", bit * width)


@pytest.mark.parametrize("width", range(2, 9))
def test_split(width):
    factory = Factory(["    .-:", f"-{width}-<", "    .-:"], native._Machine)
    for bits in inputs(width):
        factory.check(bits, bits)


@pytest.mark.parametrize(("a", "b"), itertools.product(range(1, 5), repeat=2))
def test_join_and_remove(a, b):
    for kind in (">", "%"):
        if kind == "%" and b <= a:
            continue
        factory = Factory([f"-{a}-.", f"    {kind}.-:", f"-{b}-."], native._Machine)
        for bits in inputs(a + b):
            expected = bits if kind == ">" else bits[2 * a :]
            factory.check(bits, expected)


def test_published_programs_and_exact_cycles():
    for repaired, code in ((True, PRIME_TESTER), (False, PRIME_TESTER_AS_DRAWN)):
        factory = Factory(code, native._Machine)
        for value in range(16):
            expected = str(int(value in {2, 3, 5, 7, 11, 13})) if repaired else ""
            result = factory.check(format(value, "04b"), expected)
            assert result["halted"]
            assert result["generations"] == (10 if repaired else 6)
    for code, start, period in ((FLIP_FLOP, 2, 2), (CONSTANT, 3, 1)):
        factory = Factory(code, native._Machine)
        for bits in ("", "0", "1", "01"):
            result = factory.check(bits)
            assert not result["halted"]
            assert result["cycle_start"] == start
            assert result["period"] == period


def test_mutual_links_and_crossovers():
    vectors = [(x, y) for x in (-1, 0, 1) for y in (-1, 0, 1) if (x, y) != (0, 0)]
    for a, b, (dx, dy), chain in itertools.product(
        "-|/\\.", "-|/\\.", vectors, range(5)
    ):
        points = {(0, 0): a, ((chain + 1) * dx, (chain + 1) * dy): b}
        for step in range(1, chain + 1):
            points[step * dx, step * dy] = "="
        x0 = min(x for x, y in points)
        x1 = max(x for x, y in points)
        y0 = min(y for x, y in points)
        y1 = max(y for x, y in points)
        code = [
            "".join(points.get((x, y), " ") for x in range(x0, x1 + 1))
            for y in range(y1, y0 - 1, -1)
        ]
        factory = Factory(code, native._Machine)
        for bits in ("", "0110", "1001"):
            assert factory.check(bits)["halted"]


def test_shared_input_drivers():
    factory = Factory(["-.", " |", "-.-:"], native._Machine)
    for bits in inputs(2):
        factory.check(bits, str(int(bits[0]) ^ int(bits[1])))


@pytest.mark.parametrize("width", range(1, 9))
@pytest.mark.parametrize("depth", [1, 2, 4])
def test_nested_symbolic_functions(width, depth):
    declarations = ["{invert", "-n-~-n-:", "}"]
    previous = "invert"
    for name in ("second", "third", "fourth")[: depth - 1]:
        declarations.extend(["{" + name, f"-n-{previous}-n-:", "}"])
        previous = name
    factory = Factory([*declarations, f"-{width}-{previous}-:"], native._Machine)
    for bits in inputs(width):
        factory.check(bits, "".join(str(1 - int(bit)) for bit in bits))


def test_unlabelled_nested_function():
    factory = Factory(
        ["{invert", "-1-~-1-:", "}", "{outer", "-invert-:", "}", "-outer-:"],
        native._Machine,
    )
    for bit in "01":
        factory.check(bit, str(1 - int(bit)))


@pytest.mark.parametrize("zeroes", [4300, 5000])
@pytest.mark.parametrize("width", [1, 2])
@pytest.mark.parametrize("function", [False, True])
def test_long_decimal_width(zeroes, width, function):
    label = "0" * zeroes + str(width)
    code = (
        ["{invert", f"-{label}-~-{label}-:", "}", f"-{width}-invert-:"]
        if function
        else [f"-{label}-~-:"]
    )
    Factory(code, native._Machine).check("1" * width, "0" * width)


@pytest.mark.parametrize(
    "code",
    [
        [" .--.", "  \\ |", " --a.-:", "  /", "-."],
        ["    .-:", "-1-<", "    .-:"],
        ["{empty", ")-:", "}", "-empty-:"],
        ["{three", "-:", "-:", "-:", "}", "-three-:"],
        ["{self", "-1-self-:", "}", "-self-:"],
    ],
)
def test_rejects_invalid_semantics(code):
    from esolangs.interpreters.io import ScriptedIO
    from tests.interpreters.circuit_diagram_reference import NamedReference

    with pytest.raises(ValueError):  # noqa: PT011 -- Models use independent diagnostics.
        NamedReference(code, "111")
    with pytest.raises(ValueError):  # noqa: PT011 -- Models use independent diagnostics.
        native._Machine(code, ScriptedIO("111"))


def test_recursive_failure_keeps_later_evaluations_usable():
    from esolangs.interpreters.io import ScriptedIO

    with pytest.raises(ValueError):  # noqa: PT011 -- Models use independent diagnostics.
        native._Machine(["{self", "-1-self-:", "}", "-self-:"], ScriptedIO("1"))
    Factory(["{self", "-1-~-1-:", "}", "-self-:"], native._Machine).check("1", "0")


def test_distinct_nested_clock_reads(monkeypatch):
    from esolangs.interpreters.io import ScriptedIO
    from tests.interpreters.circuit_diagram_reference import ClockTape, NamedReference

    for depth, bits, frames in itertools.product(
        (1, 2, 4), ("00", "01", "10", "11"), ((5, 6), (0, 0), ((1 << 32) - 1, 1))
    ):
        declarations = ["{c", "-:", "t-32-:", "}", "{pair", "-1-c-:", "-1-c-:", "}"]
        previous = "pair"
        for name in ("alpha", "beta", "gamma")[: depth - 1]:
            declarations.extend(["{" + name, "-n-.", f"    {previous}.-:", "-m-.", "}"])
            previous = name
        code = [*declarations, "-.", f"  {previous}.-:", "-."]
        native_frames = iter(frames)
        reference_frames = iter(frames)
        monkeypatch.setattr(
            native, "_seconds_since_2000", lambda frames=native_frames: next(frames)
        )
        clock = ClockTape(provider=lambda frames=reference_frames: next(frames))
        ref = NamedReference(code, bits, clock=clock)
        io = ScriptedIO(bits)
        m = native._Machine(code, io)
        groups = tuple(
            frozenset((col, -row) for row, col in wire.cells) for wire in m.wirings
        )
        assert set(groups) == set(ref.components)
        ordered = {(gate.kind, gate.point): gate for gate in ref.gates}
        gates = tuple(ordered[gate.kind, (gate.col, -gate.row)] for gate in m.gates)
        banked = []
        for _step in range(10):
            expected = (
                tuple(ref.values[group] for group in groups),
                tuple(ref.latches[gate] for gate in gates),
                ref.halted,
                clock.position,
            )
            assert m.snapshot() == expected
            assert (io.getvalue(), io.position(), io.past_end) == (
                ref.stdout,
                ref.offset,
                ref.past_end,
            )
            assert m.memory == [
                bit for bundle in expected[0] if bundle is not None for bit in bundle
            ]
            banked.append((m.snapshot(), expected))
            hash(m.snapshot())
            if ref.halted:
                break
            ref.step()
            m.step()
        else:
            raise TimeoutError("observation bound reached")
        assert clock.position == m.clock.position == 2
        expected_output = (
            bits[0] + format(frames[0], "032b") + bits[1] + format(frames[1], "032b")
        )
        assert io.getvalue() == expected_output
        assert all(old == expected for old, expected in banked)
        assert next(native_frames, None) is None
        assert next(reference_frames, None) is None


@pytest.mark.slow
@pytest.mark.parametrize("clocked", [False, True])
def test_deep_calls_use_heap_with_exact_state(clocked, monkeypatch):
    from esolangs.interpreters.io import ScriptedIO

    depth = 1024

    def name(index):
        letters = []
        while True:
            index, digit = divmod(index, 26)
            letters.append(chr(97 + digit))
            if not index:
                return "fn" + "".join(reversed(letters))

    names = [name(i) for i in range(depth)]
    body = ["-:", "t-32-:"] if clocked else ["-1-~-1-:"]
    code = ["{" + names[0], *body, "}"]
    for previous, current in itertools.pairwise(names):
        code.extend(["{" + current, f"-1-{previous}-:", "}"])
    code.append(f"-1-{names[-1]}-:")
    monkeypatch.setattr(native, "_seconds_since_2000", lambda: 5)
    io = ScriptedIO("1")
    m = native._Machine(code, io)
    answer = (1, *map(int, format(5, "032b"))) if clocked else (0,)
    expected = [
        (((1,), None), ((None,), (None,)), False, 0),
        ((None, answer), (((1,),), (None,)), False, int(clocked)),
        ((None, None), (((1,),), (None,)), False, int(clocked)),
        ((None, None), (((1,),), (None,)), True, int(clocked)),
    ]
    input_cells = frozenset({(0, 0), (0, 2)})
    output_cells = frozenset({(0, 3 + len(names[-1]))})
    indices = {wire.cells: i for i, wire in enumerate(m.wirings)}
    assert set(indices) == {input_cells, output_cells}
    assert [(gate.kind, gate.row, gate.col) for gate in m.gates] == [
        (names[-1], 0, 3),
        (":", 0, 4 + len(names[-1])),
    ]
    assert [wire.cells for wire in m.gates[0].inputs] == [input_cells]
    assert [wire.cells for wire in m.gates[0].outputs] == [output_cells]
    assert [wire.cells for wire in m.gates[1].inputs] == [output_cells]
    banked = []
    for step, state in enumerate(expected):
        logical, latches, halted, clock_reads = state
        values = [None, None]
        values[indices[input_cells]] = logical[0]
        values[indices[output_cells]] = logical[1]
        state = tuple(values), latches, halted, clock_reads
        assert m.snapshot() == state, (depth, clocked, step, m.snapshot(), state)
        assert io.getvalue() == ("".join(map(str, answer)) if step >= 2 else "")
        assert io.position() == 1
        assert io.past_end == 0
        assert m.memory == [
            bit for value in values if value is not None for bit in value
        ]
        assert m.ip is None
        assert m.stack == []
        banked.append((m.snapshot(), state))
        hash(m.snapshot())
        if step < 3:
            m.step()
    assert all(snapshot == state for snapshot, state in banked)


def test_clock_cursor_prevents_false_cycles(monkeypatch):
    from esolangs.interpreters.io import ScriptedIO
    from esolangs.vm import run_until_halt_or_cycle

    code = ["{c", "-1---.", "      O.-:", "t-32-.", "}", "--.c.", "   =", "  .c.--"]
    monkeypatch.setattr(native, "_seconds_since_2000", lambda: 0)
    m = native._Machine(code, ScriptedIO("1"))
    seen = {}
    frames = []
    data_repeats = []
    for step in range(16):
        monkeypatch.setattr(
            native, "_seconds_since_2000", (lambda: 0) if step < 8 else (lambda: 1)
        )
        key = m.snapshot()
        data = key[:3]
        if data in seen:
            data_repeats.append((seen[data], step))
        seen.setdefault(data, step)
        assert key not in [frame["snapshot"] for frame in frames]
        frames.append({"step": step, "snapshot": key})
        m.step()
    assert data_repeats
    assert frames[6]["snapshot"][:2] != frames[10]["snapshot"][:2]
    monkeypatch.setattr(native, "_seconds_since_2000", lambda: 0)
    try:
        run_until_halt_or_cycle(native._Machine(code, ScriptedIO("1")), limit=24)
    except TimeoutError:
        pass
    else:
        raise AssertionError("clock-consuming loop was declared an exact state cycle")
    # Activity remains independent of data, so a function body with feedback
    # can reject non-settlement even when its nested clock reads change.
    wrapped = ["{loop", *code[5:], "}", *code[:5], "-loop-:"]
    try:
        native._Machine(wrapped, ScriptedIO("1"))
    except ValueError as error:
        activity = str(error)
        assert "does not settle" in activity
    else:
        raise AssertionError("clock-consuming atomic activity cycle accepted")


@pytest.mark.parametrize("width", range(1, 6))
def test_symbols_bound_by_numeric_widths(width):
    factory = Factory(
        [f"-{width}-name-:", "-name-:"], native._Machine, symbols={"name": width}
    )
    for bits in inputs(2 * width):
        factory.check(bits, bits)
    factory = Factory([f"-{width}+free-:"], native._Machine)
    for bits in inputs(width + 1):
        factory.check(bits, bits)


@pytest.mark.parametrize(("a", "b"), itertools.product(range(1, 5), repeat=2))
def test_symbolic_sums_have_independent_bindings(a, b):
    factory = Factory(
        [f"-{a}-n-.", "      >-n+m-:", f"-{b}-m-."],
        native._Machine,
        symbols={"n": a, "m": b},
    )
    for bits in inputs(a + b):
        factory.check(bits, bits)


@pytest.mark.parametrize(("a", "b"), itertools.product(range(1, 4), repeat=2))
@pytest.mark.parametrize("kind", tuple("aAoOxX>%"))
def test_two_input_functions(a, b, kind):
    if kind == "%" and a >= b:
        return
    code = [
        "{combine",
        "-n-.",
        f"    {kind}.-:",
        "-m-.",
        "}",
        f"-{a}-.",
        "    combine.-:",
        f"-{b}-.",
    ]
    factory = Factory(code, native._Machine)
    for bits in inputs(a + b):
        count = bits.count("1")
        if kind == ">":
            expected = bits
        elif kind == "%":
            expected = bits[2 * a :]
        else:
            predicate = {"a": count == len(bits), "o": count > 0, "x": count == 1}[
                kind.lower()
            ]
            expected = str(int(predicate if kind.islower() else not predicate))
        factory.check(bits, expected)


def test_empty_quiescence_and_whitespace_eof():
    Factory([], native._Machine).check("", "")
    factory = Factory(["-4-~-:"], native._Machine)
    for bits, expected in (("", "1111"), ("1", "0111"), (" 1\n0\t1\r0 ", "0101")):
        factory.check(bits, expected)


@pytest.mark.parametrize("width", range(1, 5))
def test_overlapping_bundle_drivers(width):
    prefix = f"-{width}-"
    factory = Factory(
        [prefix + ".", " " * len(prefix) + "|", prefix + ".-:"], native._Machine
    )
    for bits in inputs(2 * width):
        expected = "".join(
            str(int(a) ^ int(b))
            for a, b in zip(bits[:width], bits[width:], strict=True)
        )
        factory.check(bits, expected)
    factory = Factory(["-.~.", "    .-:", "-.~."], native._Machine)
    for bits in inputs(2):
        factory.check(bits, str(int(bits[0]) ^ int(bits[1])))


@pytest.mark.parametrize(
    "seconds",
    [-5, 0, 1, 5, (1 << 31) - 1, 1 << 31, (1 << 32) - 1, 1 << 32, (1 << 32) + 5],
)
def test_clock_epoch_wraps_with_exact_state(seconds, monkeypatch):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is UTC
            return datetime(2000, 1, 1, tzinfo=UTC) + timedelta(seconds=seconds)

    monkeypatch.setattr(native, "datetime", FrozenDateTime)
    Factory(["t-32-:"], native._Machine, clock_seconds=seconds).check(
        "", format(seconds % (1 << 32), "032b")
    )


@pytest.mark.parametrize(("a", "b"), itertools.product(range(1, 4), repeat=2))
def test_numeric_label_sums(a, b):
    factory = Factory([f"-{a}+{b}-:"], native._Machine)
    for bits in inputs(a + b):
        factory.check(bits, bits)


@pytest.mark.parametrize("n", [1, 2, 3])
def test_direct_affine_programs(n):
    from esolangs.tools.circuit_diagram import _affine_circuit

    emitted = 0
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        source = _affine_circuit(table, 1)
        if source is None:
            continue
        emitted += 1
        factory = Factory(source.splitlines(), native._Machine)
        for row, expected in enumerate(table):
            factory.check(format(row, f"0{n}b"), expected)
    assert emitted == 1 << (n + 1)


@pytest.mark.medium
@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_every_three_input_table_under_each_selector_order(order):
    from esolangs.tools.circuit_diagram import _circuit_diagram_at

    for value in range(256):
        table = format(value, "08b")
        essential = sum(
            any(table[row] != table[row ^ (1 << bit)] for row in range(8))
            for bit in range(3)
        )
        projected_order = tuple(index for index in order if index < max(1, essential))
        factory = Factory(
            _circuit_diagram_at(table, None, projected_order).splitlines(),
            native._Machine,
        )
        for row, expected in enumerate(table):
            factory.check(format(row, "03b"), expected)


def test_direct_h_layout_small_tables():
    from esolangs.tools.circuit_diagram import _h_term_layout

    for value in range(1, 15):
        table = format(value, "04b")
        factory = Factory(_h_term_layout(table).render().splitlines(), native._Machine)
        for row, expected in enumerate(table):
            factory.check(format(row, "02b"), expected)


@pytest.mark.parametrize("draw", [0, 1, 2])
def test_direct_h_layout_quadrant_lanes(draw):
    import random

    from esolangs.tools.circuit_diagram import _h_term_layout

    rng = random.Random(4)
    for _ in range(draw + 1):
        table = "".join(rng.choice("01") for _ in range(16))
    factory = Factory(_h_term_layout(table).render().splitlines(), native._Machine)
    for row, expected in enumerate(table):
        factory.check(format(row, "04b"), expected)
