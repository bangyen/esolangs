"""Independent B-tapemark fields, Unicode source and generated programs."""

import itertools
import random

import pytest

from esolangs.interpreters.grid_based.b_tapemark import (
    _advance,
    _Grid,
    _Machine,
    _State,
)
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.b_tapemark import b_tapemark
from tests.interpreters.b_tapemark_observer import cells, check
from tests.interpreters.b_tapemark_reference import Point, Reference
from tests.interpreters.views import view as vm_view

COMMANDS = " \\/!+-*|?%0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZλ\n"
SEPARATORS = ("\v", "\f", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029")


def view(machine):
    s = machine.state
    return (
        s.program,
        s.positions,
        s.direction,
        tuple(frozenset(cells(g).items()) for g in s.grids),
        s.halted,
        machine.io.position(),
        machine.io.past_end,
        machine.io.getvalue(),
    )


def compare(machine, reference):
    assert view(machine) == reference.native_view()
    assert vm_view(machine, "ip") == (
        reference.points[reference.active].real,
        -reference.points[reference.active].imag,
    )
    assert vm_view(machine, "memory") == [
        machine.state.grids,
        machine.state.positions,
        reference.active,
    ]
    assert vm_view(machine, "stack") == []
    assert machine.io.reads == reference.offset
    assert machine.halted == reference.halted


def record_key(keys, machine, reference):
    record = reference.native_view()[:6]
    assert keys.setdefault(machine.snapshot(), record) == record, (
        "distinct future states share a snapshot"
    )


@pytest.mark.parametrize(
    "origin", [Point(0, 0), Point(-7, 11), Point(10**100, -(10**100))]
)
@pytest.mark.parametrize("direction", range(4))
@pytest.mark.parametrize("active", range(2))
@pytest.mark.parametrize("shard", range(4))
@pytest.mark.medium
def test_local_transitions(active, direction, origin, shard):
    keys = {}
    cases = itertools.product(
        COMMANDS, (" ", "0", "A", "λ"), (" ", "/", "!", "λ"), ("Z", " ", "\n", "")
    )
    for case, (opcode, datum, skipped, stdin) in enumerate(cases):
        if case % 4 != shard:
            continue
        ref = Reference(">", stdin)
        ref.active = active
        ref.heading = (1, -1j, -1, 1j)[direction]
        ref.points = [origin, origin + complex(3, 2)]
        ref.fields = [{}, {}]
        ref.fields[active][ref.points[active]] = opcode
        ref.fields[1 - active][ref.points[1 - active]] = datum
        ref.fields[active][ref.points[active] + ref.heading] = skipped
        ref.fields = [
            {p: c for p, c in field.items() if c != " "} for field in ref.fields
        ]
        initial = ref.native_view()
        state = _State(
            active,
            initial[1],
            direction,
            tuple(_Grid(dict(field)) for field in initial[3]),
        )
        machine = _Machine(">", ScriptedIO(stdin))
        machine.state = state
        compare(machine, ref)
        record_key(keys, machine, ref)
        failures = []
        for step in (machine.step, ref.step):
            try:
                step()
            except EOFError:
                failures.append(EOFError)
            else:
                failures.append(None)
        assert failures[0] is failures[1]
        compare(machine, ref)
        record_key(keys, machine, ref)
        assert (
            state.program,
            state.positions,
            state.direction,
            tuple(frozenset(cells(g).items()) for g in state.grids),
            state.halted,
        ) == initial[:5]


@pytest.mark.parametrize("symbol", [*SEPARATORS, "\t", "a", "²", "λ", ".", "_"])
def test_forbidden_source_symbols_are_rejected(symbol):
    source = ">" + symbol + "!"
    with pytest.raises(ValueError, match="invalid"):
        _Machine(source, ScriptedIO())
    with pytest.raises(ValueError, match="invalid"):
        Reference(source)


@pytest.mark.parametrize("symbol", [*SEPARATORS, "\t", "a", "²", "λ", "><^v\\/!?"])
def test_quoted_source_occupies_columns_without_becoming_rows(symbol):
    check('>A"' + symbol + '"B!', "", "AB")


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
def test_standard_source_rows_and_ragged_edges(ending):
    check(ending.join(["", "  >A\\", "    !", ""]), "", "A")


@pytest.mark.parametrize(
    ("source", "message"), [("!", "start"), ("> <!", "start"), ('>"', "quote")]
)
def test_loading_rejects_ambiguous_starts_and_quotes(source, message):
    with pytest.raises(ValueError, match=message):
        _Machine(source, ScriptedIO())
    with pytest.raises(ValueError, match=r"start|comment"):
        Reference(source)


@pytest.mark.parametrize(
    ("source", "stdin", "expected"),
    [
        (">HELLO+WORLD!", "", "HELLO WORLD"),
        (">*A+!", "", "A"),
        (">-+!", "Z", "Z"),
        (">-+!", "λ", "λ"),
        (">-+!", "\n", "\n"),
        (">-*+!", "A", ""),
    ],
)
def test_published_and_character_input_examples(source, stdin, expected):
    check(source, stdin, expected)


@pytest.mark.parametrize("stdin", ["", "A\nB\n", " ", "λ", "\v\x85\u2028"])
def test_published_cat_preserves_every_character_until_eof(stdin):
    source = "/>-+|\\\n\\    /"
    machine = _Machine(source, ScriptedIO(stdin))
    ref = Reference(source, stdin)
    for _ in range(256):
        before = machine.snapshot()
        try:
            ref.step()
        except EOFError:
            with pytest.raises(EOFError):
                machine.step()
            assert machine.snapshot() == before
            compare(machine, ref)
            assert machine.io.getvalue() == stdin
            assert machine.io.position() == len(stdin)
            assert machine.io.past_end == 1
            return
        machine.step()
        compare(machine, ref)
    pytest.fail("EOF execution bound reached; outcome unverified")


@pytest.mark.parametrize(("source", "period"), [("/>\\\n\\ /", 6), ("/>+\\\n\\  /", 8)])
def test_closed_routes_have_independent_repeat_certificates(source, period):
    from esolangs.vm import run_until_halt_or_cycle

    ref = Reference(source)
    machine = _Machine(source, ScriptedIO())
    initial = ref.native_view()[:6]
    snapshot = machine.snapshot()
    for _ in range(period):
        ref.step()
        machine.step()
        compare(machine, ref)
    assert ref.native_view()[:6] == initial
    assert machine.snapshot() == snapshot
    assert machine.halted is False
    driven = _Machine(source, ScriptedIO())
    assert run_until_halt_or_cycle(driven, limit=100) is False
    assert driven.io.position() == 0
    assert _Machine(">!", ScriptedIO()).halted is False
    assert run_until_halt_or_cycle(_Machine(">!", ScriptedIO()), limit=100) is True


def test_translating_blank_tail_remains_inconclusive():
    from esolangs.vm import run_until_halt_or_cycle

    machine = _Machine(">", ScriptedIO())
    ref = Reference(">")
    for step in range(32):
        ref.step()
        machine.step()
        compare(machine, ref)
        assert ref.points[0] == Point(step + 1, 0)
        assert ref.fields == [{}, {}]
    with pytest.raises(TimeoutError, match="undecided"):
        run_until_halt_or_cycle(_Machine(">", ScriptedIO()), limit=64)


def test_snapshot_distinguishes_program_heading_and_input_cursor():
    keys = {}
    for source in (">", "<", "^", "v", ">-+!"):
        for active, consumed in itertools.product(range(2), range(3)):
            ref = Reference(source, "ABC")
            ref.active = active
            ref.offset = consumed
            io = ScriptedIO("ABC")
            for _ in range(consumed):
                io.input_char()
            machine = _Machine(source, io)
            state = machine.state
            machine.state = _State(
                active, state.positions, state.direction, state.grids
            )
            compare(machine, ref)
            record_key(keys, machine, ref)


@pytest.mark.parametrize(
    ("n", "start"),
    [(n, start) for n in (1, 2, 3) for start in range(0, 1 << (1 << n), 16)],
)
def test_generated_small_tables(n, start):
    for value in range(start, min(start + 16, 1 << (1 << n))):
        table = format(value, f"0{1 << n}b")
        sources = {b_tapemark(table, width) for width in (None, 1, 13, 100)}
        for source in sources:
            for row, answer in enumerate(table):
                check(source, format(row, f"0{n}b"), answer)


@pytest.mark.parametrize("n", [4, 5, 6])
@pytest.mark.parametrize("width", [1, 9, 19, 80, 10000])
def test_existing_weighted_layouts_have_independent_state_checks(n, width):
    table = "".join(str((row * 17 + row // 3).bit_count() % 2) for row in range(1 << n))
    source = b_tapemark(table, width)
    for row, answer in enumerate(table):
        check(source, format(row, f"0{n}b"), answer)


@pytest.mark.parametrize("vertical", [False, True])
def test_sparse_builder_axes_execute_after_coordinate_compression(vertical):
    from esolangs.tools.b_tapemark import _Builder

    builder = _Builder()
    builder.put(0, 0, "v" if vertical else ">")
    builder.put(0 if vertical else 100, 100 if vertical else 0, "!")
    check(builder.render(), "", "")


@pytest.mark.parametrize("as_string", [False, True])
@pytest.mark.parametrize("width", [None, 1, 13, 100])
def test_public_generator_and_driver(as_string, width):
    import esolangs

    table = "01101001"
    source = esolangs.generate("B-tapemark", table, width)
    if as_string:
        source = str(source)
    for row, answer in enumerate(table):
        assert esolangs.run("B-tapemark", source, format(row, "03b")) == answer


def wide_table(n, kind):
    size = 1 << n
    if kind == "zero":
        return "0" * size
    if kind == "one":
        return "1" * size
    if kind == "first":
        return "0" * (size // 2) + "1" * (size // 2)
    if kind == "last":
        return "01" * (size // 2)
    if kind == "parity":
        return "".join(str(row.bit_count() & 1) for row in range(size))
    rng = random.Random(731 + n)
    return "".join(str(rng.randrange(2)) for _ in range(size))


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "kind", "start"),
    [
        (n, kind, start)
        for n in range(4, 11)
        for kind in ("zero", "one", "first", "last", "parity", "seeded")
        for start in range(0, 1 << n, 4)
    ],
)
def test_generated_wide_tables(n, kind, start):
    table = wide_table(n, kind)
    sources = {b_tapemark(table, width) for width in (None, 1, 13, 100)}
    for source in sources:
        for row in range(start, start + 4):
            check(source, format(row, f"0{n}b"), table[row])


@pytest.mark.parametrize("source", [">-+!", ">--+!"])
def test_occupied_data_preserves_unread_input(source):
    check(source, "Z\nignored", "Z", consume_all=False)


def test_halted_transition_preserves_fields_and_unread_input():
    io = ScriptedIO("unused")
    machine = _Machine(">!", io)
    reference = Reference(">!", "unused")
    for _ in range(2):
        reference.step()
        machine.step()
        compare(machine, reference)
    assert reference.halted
    previous = machine.snapshot()
    machine.state, output = _advance(machine.state, "Z")
    assert output is None
    reference.step()
    compare(machine, reference)
    machine.step()
    compare(machine, reference)
    assert machine.snapshot() == previous
