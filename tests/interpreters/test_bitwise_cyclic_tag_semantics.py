"""Independent rotating instructions and destructive data-string deletion."""

import itertools
import random

import pytest

import esolangs
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.queue_based.bitwise_cyclic_tag import _Machine, run
from tests.interpreters.views import view as vm_view


def parse(code):
    text = "".join(code.split())
    if set(text) - set("01,") or text.count(",") > 1:
        raise ValueError("invalid source")
    program, _, data = text.partition(",")
    offsets = []
    for at, char in enumerate(code):
        if char == ",":
            break
        if not char.isspace():
            offsets.append(at)
    return program, data, offsets


def reference(code, cap):
    ring, data, offsets = parse(code)
    size = len(ring)
    head = deleted = 0
    answer = None
    for _ in range(cap):
        if not ring or not data:
            break
        if ring[0] == "0":
            answer, data = data[0], data[1:]
            deleted += 1
            width = 1
        else:
            if data[0] == "1":
                data += (ring + ring)[1]
            width = 2
        shift = width % size
        ring = ring[shift:] + ring[:shift]
        head = (head + width) % size
    halted = not ring or not data
    output = answer if halted and answer is not None else ""
    return output, data, head, deleted, answer, offsets[head] if size else None, halted


def observe(code, cap):
    io = ScriptedIO("unused λ")
    machine = _Machine(code, io)
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
    assert io.getvalue() == ""
    if machine.halted:
        machine.step()
        output = io.getvalue()
        snapshot = machine.snapshot()
        machine.step()
        machine.step()
        assert io.getvalue() == output
        assert machine.snapshot() == snapshot
    assert io.position() == 0
    assert vm_view(machine, "stack") == []
    assert vm_view(machine, "memory") == list(map(int, machine.live))
    return (
        io.getvalue(),
        machine.live,
        machine.head,
        machine.read,
        machine.answer,
        vm_view(machine, "ip"),
        machine.halted,
    )


def corpus():
    programs = [
        "".join(bits) for n in range(5) for bits in itertools.product("01", repeat=n)
    ]
    data = [
        "".join(bits) for n in range(4) for bits in itertools.product("01", repeat=n)
    ]
    for program, queue in itertools.product(programs, data):
        yield program + "," + queue
    yield from programs
    yield from [
        "0 0\n,\t1 0",
        "\u2003 1\n0 0 0, 1\t1",
        "00111,101",
        " , ",
        "2,1",
        "00,1,1",
        "0,x",
    ]
    rng = random.Random(1708)
    for _ in range(32):
        yield "".join(rng.choices("01", k=9)) + "," + "".join(rng.choices("01", k=9))


@pytest.mark.parametrize("cap", [0, 1, 2, 9, 80])
def test_bounded_states_match_independent_rotating_strings(cap):
    for code in corpus():
        try:
            expected = reference(code, cap)
        except ValueError:
            with pytest.raises(ValueError, match="Bitwise Cyclic Tag"):
                observe(code, cap)
        else:
            assert observe(code, cap) == expected, (code, cap)


def test_run_matches_halting_reference():
    for code in corpus():
        try:
            expected = reference(code, 80)
        except ValueError:
            continue
        if expected[-1]:
            io = ScriptedIO("unused")
            run(code, io)
            assert io.getvalue() == expected[0], code
            assert io.position() == 0


@pytest.mark.parametrize(
    ("code", "output"),
    [
        ("0,1", "1"),
        ("0,0", "0"),
        ("00,10", "0"),
        ("00,01", "1"),
        ("1000,11", "0"),
        ("1000,01", "1"),
        ("0011,", ""),
        ("0011", ""),
        (",1011", ""),
        ("0 0\n,\t1 0", "0"),
    ],
)
def test_reference_positive_controls(code, output):
    expected = reference(code, 80)
    assert expected[0] == output
    assert expected[-1]
    assert observe(code, 80) == expected


def test_step_cap_does_not_prove_a_halt():
    for code in ("1,1", "11,0", "00111,101"):
        expected = reference(code, 80)
        assert not expected[-1]
        assert expected[0] == ""
        assert observe(code, 80) == expected
    growing = reference("1,1", 80)
    assert len(growing[1]) == 81


def test_snapshot_distinguishes_appends_at_equal_program_and_read_positions():
    machine = _Machine("11,1", ScriptedIO())
    before = machine.snapshot()
    cursor = machine.head, machine.read
    machine.step()
    assert (machine.head, machine.read) == cursor
    assert machine.live == "11"
    assert machine.snapshot() != before


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table_in_independent_engine(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        template = esolangs.generate("Bitwise Cyclic Tag", table)
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            code = esolangs.instantiate("Bitwise Cyclic Tag", template, bits)
            result = reference(code, 10_000)
            assert result[-1], (table, row)
            assert result[0] == answer, (table, row)
            assert observe(code, 10_000) == result, (table, row)
            io = ScriptedIO("unused")
            run(code, io)
            assert io.getvalue() == answer
            assert io.position() == 0
