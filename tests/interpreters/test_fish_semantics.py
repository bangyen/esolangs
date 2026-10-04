"""Fish agrees with an independent compass and immutable stack model."""

import copy
import itertools
import random

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.fish import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.fish import fish
from tests.interpreters.fish_reference import FishError, Reference


class Draws:
    def __init__(self, choice):
        self.choice = choice
        self.calls = []

    def randbelow(self, upper):
        self.calls.append(upper)
        return self.choice


def check_instruction(
    op,
    values=(),
    *,
    rows=None,
    position=(0, 0),
    heading=0,
    scopes=None,
    registers=None,
    quote=None,
    stdin="",
    choice=0,
    cells=None,
):
    rows = [op] if rows is None else rows
    ref = Reference(rows, stdin)
    ref.position = position
    ref.heading = heading
    ref.scopes = (tuple(values),) if scopes is None else scopes
    ref.registers = (None,) * len(ref.scopes) if registers is None else registers
    ref.quote = quote
    io = ScriptedIO(stdin)
    draw = Draws(choice)
    machine = _Machine(rows, io, draw)
    machine.x, machine.y = position
    machine.dx, machine.dy = ref.movement()
    machine.stacks = [list(scope) for scope in ref.scopes]
    machine.registers = list(ref.registers)
    machine.quote = quote
    if cells is not None:
        ref.cells = {**ref.cells, **cells}
        machine.cells.update(cells)
    reference_error = native_error = False
    try:
        ref.step(choice)
    except FishError:
        reference_error = True
    try:
        machine.step()
    except HaltError:
        native_error = True
    assert native_error == reference_error, (op, values, position, heading, "error")
    assert machine.snapshot() == ref.view(), (op, values, position, heading, "state")
    assert machine.stack == list(ref.scopes[-1])
    assert machine.ip == (
        None if ref.done else (ref.position[1], ref.position[0], *ref.movement())
    )
    assert (io.getvalue(), io.position(), io.past_end, draw.calls) == (
        ref.output,
        ref.offset,
        ref.past_end,
        ref.draws,
    ), (op, values, "effects")


def runtime(machine):
    return (
        machine.x,
        machine.y,
        machine.dx,
        machine.dy,
        tuple(map(tuple, machine.stacks)),
        tuple(machine.registers),
        machine.quote,
        machine.halted,
        machine.width,
        machine.height,
        machine.io.position(),
    )


def ref_runtime(reference):
    full = reference.view()
    return (*full[:4], *full[5:])


def check(rows, stdin="", *, choice=0, full=True, limit=30000):
    ref = Reference(rows, stdin)
    io = ScriptedIO(stdin)
    draw = Draws(choice)
    machine = _Machine(rows, io, draw)
    seen = {}
    for step in range(limit):
        state = ref.view()
        assert machine.stack == list(ref.scopes[-1])
        assert machine.ip == (
            None if ref.done else (ref.position[1], ref.position[0], *ref.movement())
        )
        assert runtime(machine) == ref_runtime(ref), (rows, stdin, step, "runtime")
        if full or ref.done:
            assert machine.snapshot() == state, (rows, stdin, step, "full state")
        assert (io.getvalue(), io.position(), io.past_end, draw.calls) == (
            ref.output,
            ref.offset,
            ref.past_end,
            ref.draws,
        ), (rows, stdin, step, "effects")
        if ref.done:
            break
        if state in seen:
            assert machine.snapshot() == state
            break
        seen[state] = step
        reference_error = native_error = False
        try:
            ref.step(choice)
        except FishError:
            reference_error = True
        try:
            machine.step()
        except HaltError:
            native_error = True
        assert native_error == reference_error, (rows, stdin, step, "error")
        if reference_error:
            assert machine.snapshot() == ref.view()
            assert io.getvalue() == ref.output
            break
    else:
        raise AssertionError(("bounded execution", rows))
    return ref


def test_arithmetic_transition_domain():
    numbers = (-5, -2, -1, 0, 1, 2, 3, 7, 15, 16, 1.5, -2.5, 0.0, 1.0, 2**65, 2**1024)
    for left, right, op in itertools.product(numbers, numbers, "+-*,%()="):
        check_instruction(op, (left, right))


@pytest.mark.parametrize("op", "0123456789abcdef><^v/\\|_#x!? .:~$@}{rl[]&gpon;'\"z")
def test_instruction_domains(op):
    for count in range(4):
        for values in itertools.product((0, 1, 2), repeat=count):
            for heading in range(4):
                check_instruction(op, values, heading=heading)


def test_codebox_geometry_and_quotes():
    for width, height in itertools.product((1, 2, 3), repeat=2):
        for x, y in itertools.product(range(width), range(height)):
            for op, heading in itertools.product("><^v/\\|_#x!.", range(4)):
                rows = [" " * width for _ in range(height)]
                rows[y] = rows[y][:x] + op + rows[y][x + 1 :]
                for choice in range(4) if op == "x" else (0,):
                    check_instruction(
                        op,
                        (x, y),
                        rows=rows,
                        position=(x, y),
                        heading=heading,
                        choice=choice,
                    )
    for op, quote, heading in itertools.product("ix;012'\" ", ("'", '"'), range(4)):
        check_instruction(op, (1, 2), quote=quote, heading=heading)


def test_scopes_coordinates_and_io():
    # The old A-at-(0,1) control also had A at (1,0), masking transposition.
    for x, y in itertools.product(range(-1, 4), repeat=2):
        check_instruction("g", (x, y), rows=["gAB", "CDE"])
        check_instruction("p", (83, x, y), rows=["pAB", "CDE"])
    for op, scopes, registers in itertools.product(
        "[]&rl@",
        (((), ()), ((1, 2), (3,)), ((1,), (2, 3), (4, 5))),
        ((None, None, None), (0, 1, 2), (1.5, -2.5, 0)),
    ):
        check_instruction(op, scopes=scopes, registers=registers[: len(scopes)])
    for op, values in itertools.product(
        "[]gpo.", ((1.5,), (1, -2.5), (2.5, 0, 0), (-1,), (0x110000,), (0, 1, 2))
    ):
        check_instruction(op, values)
    for stdin in ("", "A", "\n", "é🙂"):
        check_instruction("i", stdin=stdin)
    for value in (-1, 0, 0x10FFFF, 0x110000):
        check_instruction(" ", cells={(0, 0): value})


def test_composed_arithmetic_and_scopes():
    for left, right, op in itertools.product(
        "0123456789abcdef", "0123456789abcdef", "+-*,%()="
    ):
        check([left + right + op + "n;"])
    for count in range(4):
        for values in itertools.product("012", repeat=count):
            for op in (
                "r",
                "}",
                "{",
                "0[]",
                "1[&]&",
                "2[r]",
                "0[1]",
                "0[0[2]]",
                "&",
                "&~&",
                "&0[1&]&",
                "3[r]r",
            ):
                check(["".join(values) + op + "ln;"])


@pytest.mark.parametrize(
    "code",
    [
        "'A'01p01go;",
        "'A'01-01-p01-01-go;",
        "'A'99p99go;",
        "'9'00p00gn;",
        "01-60p;",
        "'ix;o'roooo;",
        "42,n;",
        "01-0.;",
        "01-o;",
        "20.9n;",
        "0?11ln;",
        "1?11ln;",
    ],
)
def test_execution_controls(code):
    check([code])


def test_character_input_and_published_cat():
    for stdin in ("", "A", "\n", "é🙂\n"):
        for code in ("i:0(?;o", "iin;", "iioo;"):
            check([code], stdin)


def test_numeric_output_and_failure_controls():
    for code, values in [
        ("n;", (10**5000,)),
        ("n;", (float("inf"),)),
        ("n;", (float("-inf"),)),
        ("n;", (float("nan"),)),
        (",;", (2**1024, 1)),
        ("*;", (1e308, 1e308)),
        ("p;", (0x110000, 1, 0)),
    ]:
        ref = Reference([code])
        ref.scopes = (values,)
        io = ScriptedIO("")
        machine = _Machine([code], io)
        machine.stacks = [list(values)]
        for _ in range(30):
            assert machine.snapshot() == ref.view()
            assert io.getvalue() == ref.output
            if ref.done:
                break
            ref_error = native_error = False
            try:
                ref.step()
            except FishError:
                ref_error = True
            try:
                machine.step()
            except HaltError:
                native_error = True
            assert ref_error == native_error
            if ref_error:
                assert machine.snapshot() == ref.view()
                break
        else:
            raise AssertionError("control failed to stop")
        assert io.getvalue() == ref.output


@pytest.mark.parametrize("width", [None, 1, 2, 3, 4, 5, 7, 13, 40, 80])
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.medium
def test_generated_small_tables(n, width):
    for value in range(1 << (1 << n)):
        table = f"{value:0{1 << n}b}"
        program = fish(table, width)
        for row, answer in enumerate(table):
            ref = check(program.splitlines(), f"{row:0{n}b}", full=False)
            assert ref.done
            assert (ref.output, ref.offset, ref.past_end) == (answer, n, 0)


@pytest.mark.parametrize("width", [1, 3, 7, 13, 80])
@pytest.mark.parametrize("n", [4, 5, 6, 8, 10])
@pytest.mark.medium
def test_generated_wider_tables(n, width):
    size = 1 << n
    tables = [
        "0" * size,
        "1" * size,
        "".join(str(row.bit_count() % 2) for row in range(size)),
        "0" * (size - 1) + "1",
        "1" + "0" * (size - 1),
    ]
    if n <= 6:
        rng = random.Random(10403 + n)
        tables.append("".join(str(rng.randrange(2)) for _ in range(size)))
    for table in tables:
        program = fish(table, width)
        selected = (
            range(size)
            if n <= 6
            else sorted(
                {
                    0,
                    1,
                    size // 2 - 1,
                    size // 2,
                    size - 2,
                    size - 1,
                    *(1 << bit for bit in range(n)),
                }
            )
        )
        for row in selected:
            ref = check(program.splitlines(), f"{row:0{n}b}", full=False)
            assert ref.done
            assert (ref.output, ref.offset, ref.past_end) == (table[row], n, 0)


def test_public_run_forwards_character_io():
    code = "i:0(?;o"
    ref = check([code], "A\né🙂")
    io = ScriptedIO(ref.stdin)
    run([code], io)
    assert (io.getvalue(), io.position(), io.past_end) == (
        ref.output,
        ref.offset,
        ref.past_end,
    )


def test_branching_preserves_complete_state():
    for rows, prefix, stdin in [
        ("'i';", 1, ""),
        ("'x';", 1, ""),
        ("ia;", 1, "A"),
        ("080p", 4, ""),
        ("088p", 4, ""),
        ("000p", 4, ""),
        (";", 1, ""),
    ]:
        ref = Reference([rows], stdin)
        live = _Machine([rows], ScriptedIO(stdin))
        for _ in range(prefix):
            ref.step(0)
            live.step()
        assert live.branching_snapshot() == live.snapshot() == ref.view()
        if live.halted:
            before = live.snapshot()
            live.step()
            assert live.snapshot() == before
        base = _Machine([rows], ScriptedIO(stdin))
        parent = base.snapshot()
        result = base.branching_successors(live.snapshot(), 100)
        if not ref.done:
            ref.step(0)
        assert result == (ref.view(),), (rows, result, ref.view())
        assert base.snapshot() == parent
    for width, height in itertools.product(range(1, 4), repeat=2):
        for x, y in itertools.product(range(width), range(height)):
            for heading in range(4):
                rows = [";" * width for _ in range(height)]
                rows[y] = rows[y][:x] + "x" + rows[y][x + 1 :]
                ref = Reference(rows, "")
                ref.position = (x, y)
                ref.heading = heading
                live = _Machine(rows, ScriptedIO(""))
                live.x, live.y = ref.position
                live.dx, live.dy = ref.movement()
                expected = []
                for choice in range(4):
                    branch = copy.deepcopy(ref)
                    branch.step(choice)
                    expected.append(branch.view())
                before = live.snapshot()
                assert live.branching_successors(before, 100) == tuple(expected)
                assert live.snapshot() == before
    ref = _Machine(["i;"], ScriptedIO("A"))
    assert ref.branching_successors(ref.snapshot(), 100) is None
    assert ref.io.position() == 0


def test_all_draw_halting_and_cycle_certificates():
    for rows, expected in [
        (["x;", ";;"], (True, False)),
        (["x;"], (True, True)),
        (["x"], (False, True)),
    ]:
        start = Reference(rows)
        states = [start]
        keys = {start.view(): 0}
        edges = []
        index = 0
        while index < len(states):
            current = states[index]
            successors = []
            if not current.done:
                for choice in range(4) if current.instruction() == "x" else (0,):
                    branch = copy.deepcopy(current)
                    branch.step(choice)
                    machine = _Machine(rows, ScriptedIO(""))
                    result = machine.branching_successors(current.view(), 100)
                    assert result is not None
                    assert (
                        result[choice if current.instruction() == "x" else 0]
                        == branch.view()
                    )
                    key = branch.view()
                    if key not in keys:
                        keys[key] = len(states)
                        states.append(branch)
                    successors.append(keys[key])
            edges.append(tuple(successors))
            index += 1
            assert len(states) <= 25
        reachable = [[False] * len(states) for _ in states]
        for source, targets in enumerate(edges):
            for target in targets:
                reachable[source][target] = True
        for middle in range(len(states)):
            for source in range(len(states)):
                for target in range(len(states)):
                    reachable[source][target] |= (
                        reachable[source][middle] and reachable[middle][target]
                    )
        can_halt = any(
            state.done and reachable[0][index] for index, state in enumerate(states)
        )
        can_loop = any(
            reachable[index][index] and (index == 0 or reachable[0][index])
            for index in range(len(states))
        )
        assert (can_halt, can_loop) == expected
