"""Independent complex-coordinate walk; esolangs.org/wiki/ArrowQueue."""

import itertools
import random
from collections import deque

import pytest

import esolangs
from esolangs.interpreters.grid_based.arrowqueue import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from tests.interpreters.views import view as vm_view

_HEADINGS = {1: 0, 1j: 1, -1: 2, -1j: 3}


def reference(code, cap, placed=None, *, detect_cycle=False):
    width = max((len(line) for line in code), default=0)
    cells = {
        complex(x, y): char
        for y, line in enumerate(code)
        for x, char in enumerate(line)
    }
    point = complex(placed[1], placed[0]) if placed else 0j
    direction = 1 + 0j
    queue = deque()
    done = not code
    seen = {}
    cycle_start = None
    steps = 0
    for _ in range(cap):
        if done:
            break
        state = point, direction, tuple(queue)
        if detect_cycle and state in seen:
            cycle_start = seen[state]
            break
        seen[state] = steps
        steps += 1
        if not (0 <= point.real < width and 0 <= point.imag < len(code)):
            done = True
            break
        command = cells.get(point, " ")
        if command == "*":
            direction *= 1j
        elif command == "~":
            queue.append(direction)
        elif command == "+":
            if not queue:
                done = True
                break
            direction = queue.popleft()
        point += direction
        done = not (0 <= point.real < width and 0 <= point.imag < len(code))
    numbers = tuple(_HEADINGS[heading] for heading in queue)
    output = " ".join(map(str, numbers)) if done else ""
    result = (
        output,
        int(point.imag),
        int(point.real),
        _HEADINGS[direction],
        numbers,
        done,
    )
    return result, cycle_start, steps


def observe(code, cap, placed=None):
    io = ScriptedIO("unused")
    machine = _Machine(code, io)
    if placed:
        machine.place(*placed)
    assert isinstance(machine.halted, bool)
    for _ in range(cap):
        if machine.halted:
            break
        machine.step()
    assert io.getvalue() == ""
    assert io.position() == 0
    assert vm_view(machine, "memory") == []
    assert vm_view(machine, "stack") == list(machine.queue)
    assert vm_view(machine, "ip") == (machine.row, machine.col, machine.d)
    if machine.halted:
        snapshot = machine.snapshot()
        machine.step()
        output = io.getvalue()
        assert machine.dumped
        machine.step()
        machine.step()
        assert io.getvalue() == output
        assert machine.snapshot() == snapshot
    return (
        io.getvalue(),
        machine.row,
        machine.col,
        machine.d,
        tuple(vm_view(machine, "stack")),
        machine.halted,
    )


def corpus():
    for n in range(5):
        for cells in itertools.product("*~+.", repeat=n):
            yield ["".join(cells)]
    for cells in itertools.product("*~+.", repeat=4):
        yield ["".join(cells[:2]), "".join(cells[2:])]
    yield from [
        [],
        [""],
        ["", ""],
        ["   "],
        ["..."],
        ["*"],
        ["*", "~+"],
        ["~**", "*~*", "***"],
        [" ~*", "+ *", "*~+"],
        [" ~*", "+~*", "*~+"],
        ["~*+"],
        ["~~"],
        ["*", "", "~+"],
        ["*", "xλ?", "+"],
        ["**", "*~"],
    ]
    rng = random.Random(1711)
    for _ in range(32):
        yield [
            "".join(rng.choices("*~+. λ", k=rng.randrange(7)))
            for _ in range(rng.randrange(5))
        ]


@pytest.mark.parametrize("cap", [0, 1, 2, 9, 80])
def test_bounded_states_match_independent_complex_walk(cap):
    for code in corpus():
        expected, _, _ = reference(code, cap)
        assert observe(code, cap) == expected, (code, cap)


def test_run_matches_proven_halting_reference():
    for code in corpus():
        expected, _, _ = reference(code, 80)
        if expected[-1]:
            io = ScriptedIO("unused")
            run(code, io)
            assert io.getvalue() == expected[0], code
            assert io.position() == 0


@pytest.mark.parametrize(
    ("code", "state", "steps"),
    [
        (["..."], (0, 3, 0, ()), 3),
        (["*"], (1, 0, 1, ()), 1),
        (["*", "~+"], (2, 0, 1, (1,)), 2),
        (["~**", "*~*", "***"], (-1, 0, 3, (0, 1, 0, 3, 2, 3)), 17),
        (["~*+"], (1, 1, 1, (0,)), 2),
        (["~~"], (0, 2, 0, (0, 0)), 2),
        (["+"], (0, 0, 0, ()), 1),
    ],
)
def test_reference_positive_controls(code, state, steps):
    expected, _, count = reference(code, 80)
    assert expected[1:5] == state
    assert count == steps
    assert expected[-1]
    assert observe(code, 80) == expected
    io = ScriptedIO("unused")
    run(code, io)
    assert io.getvalue() == expected[0]
    assert io.position() == 0


@pytest.mark.parametrize("placed", [(-1, 0), (0, -1), (0, 3), (2, 0), (1, 3), (3, 4)])
def test_placed_pointer_halts_before_reading(placed):
    code = ["...", "..."]
    expected, _, count = reference(code, 1, placed)
    assert count == 1
    assert expected[1:3] == placed
    assert expected[-1]
    assert observe(code, 1, placed) == expected


def test_cycle_certificate_requires_the_full_queue():
    loop = [" ~*", "+~*", "*~+"]
    result, start, steps = reference(loop, 80, detect_cycle=True)
    assert not result[-1]
    assert start is not None
    assert observe(loop, steps) == result
    assert observe(loop, start)[1:] == result[1:]
    growing = ["*~*", "~.~", "*~*"]
    result, start, _ = reference(growing, 80, (0, 1), detect_cycle=True)
    assert not result[-1]
    assert start is None
    assert len(result[4]) == 40
    assert observe(growing, 80, (0, 1)) == result
    machine = _Machine(growing, ScriptedIO())
    machine.place(0, 1)
    before = machine.snapshot()
    cursor = vm_view(machine, "ip")
    for _ in range(8):
        machine.step()
    assert vm_view(machine, "ip") == cursor
    assert len(machine.queue) == 4
    assert machine.snapshot() != before


def test_snapshot_distinguishes_heading_at_equal_position_and_queue():
    machine = _Machine(["..."], ScriptedIO())
    before = machine.snapshot()
    machine.state = (0, 0, 1, (), False)
    assert machine.snapshot() != before


@pytest.mark.medium
@pytest.mark.parametrize("n", [1, 2, 3])
def test_every_small_generated_table_in_independent_engine(n):
    for value in range(1 << (1 << n)):
        table = format(value, f"0{1 << n}b")
        program = esolangs.generate("ArrowQueue", table)
        for row, answer in enumerate(table):
            bits = [int(bit) for bit in format(row, f"0{n}b")]
            code = esolangs.instantiate("ArrowQueue", program, bits).split("\n")
            result, start, steps = reference(code, 100_000, detect_cycle=True)
            assert result[-1] or start is not None, (table, row)
            assert str(int(start is not None)) == answer, (table, row)
            assert observe(code, steps) == result, (table, row)
            if start is None:
                io = ScriptedIO("unused")
                run(code, io)
                assert io.getvalue() == result[0]
                assert io.position() == 0
            else:
                assert observe(code, start)[1:] == result[1:], (table, row)
