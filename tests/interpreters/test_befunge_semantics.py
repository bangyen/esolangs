"""Befunge state transitions agree with an independent flat-torus model."""

import copy
import itertools
import random
from collections import deque

import pytest

import esolangs
from esolangs.exceptions import HaltError
from esolangs.interpreters.grid_based.befunge import _advance, _Machine, run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.befunge import befunge
from tests.interpreters.befunge_reference import (
    ArithmeticFaultError,
    BadNumberError,
    MissingInputError,
    Reference,
)


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
    position=(0, 0),
    heading=0,
    string=False,
    stdin="",
    choice=0,
    rows=None,
):
    if rows is None:
        rows = [" " * 80 for _ in range(25)]
        x, y = position
        rows[y] = rows[y][:x] + op + rows[y][x + 1 :]
    ref = Reference(rows, stdin)
    ref.position = complex(*position)
    ref.direction = 1j**heading
    ref.values = values
    ref.string = string
    io = ScriptedIO(stdin)
    draw = Draws(choice)
    machine = _Machine(rows, io, draw)
    cursor = (*position, int(ref.direction.real), int(ref.direction.imag))
    machine.state = (cursor, machine.state[1], list(values), string, False)
    expected = actual = None
    try:
        ref.step(choice)
    except ArithmeticFaultError:
        expected = "runtime"
    except MissingInputError:
        expected = "eof"
    except BadNumberError:
        expected = "value"
    try:
        machine.step()
    except HaltError:
        actual = "runtime"
    except EOFError:
        actual = "eof"
    except ValueError:
        actual = "value"
    assert actual == expected, (op, values, position, heading, stdin, actual, expected)
    assert machine.snapshot() == ref.view(), (op, values, position, heading, "state")
    assert (io.getvalue(), io.position(), io.past_end, draw.calls) == (
        ref.output,
        ref.offset,
        ref.past_end,
        ref.draws,
    ), (op, values, "effects")
    assert machine.stack == list(ref.values)
    assert machine.ip == (
        None
        if ref.done
        else (
            int(ref.position.imag),
            int(ref.position.real),
            int(ref.direction.real),
            int(ref.direction.imag),
        )
    )


def runtime(machine):
    cursor, _grid, stack, string, done = machine.state
    return (*cursor, tuple(stack), string, done, machine.io.position())


def check(rows, stdin="", *, choice=0, full=True):
    ref = Reference(rows, stdin)
    io = ScriptedIO(stdin)
    draw = Draws(choice)
    machine = _Machine(rows, io, draw)
    seen = {}
    for count in range(10000):
        expected = ref.view()
        assert runtime(machine) == (*expected[:4], *expected[5:]), (
            rows,
            count,
            "runtime",
        )
        if full or ref.done:
            assert machine.snapshot() == expected, (rows, count, "grid")
        assert (io.getvalue(), io.position(), io.past_end, draw.calls) == (
            ref.output,
            ref.offset,
            ref.past_end,
            ref.draws,
        )
        if ref.done:
            break
        if expected in seen:
            break
        seen[expected] = count
        wanted = actual = None
        try:
            ref.step(choice)
        except ArithmeticFaultError:
            wanted = "runtime"
        except MissingInputError:
            wanted = "eof"
        except BadNumberError:
            wanted = "value"
        try:
            machine.step()
        except HaltError:
            actual = "runtime"
        except EOFError:
            actual = "eof"
        except ValueError:
            actual = "value"
        assert actual == wanted, (rows, count, actual, wanted)
        if wanted:
            assert machine.snapshot() == ref.view()
            assert io.getvalue() == ref.output
            assert io.past_end == ref.past_end
            break
    else:
        raise AssertionError("bounded execution did not finish or revisit full state")
    return ref


def test_arithmetic_and_word_boundaries():
    base = Reference(["@"])
    lo, hi = base.lower, base.upper
    for numbers, stdin in [
        ((-9, -2, -1, 0, 1, 2, 9), "7"),
        ((lo, lo + 1, -1, 0, 1, hi - 1, hi), "-7"),
    ]:
        for left, right, op in itertools.product(numbers, numbers, "+-*/%`"):
            check_instruction(op, (left, right), stdin=stdin)


@pytest.mark.parametrize("op", '0123456789+-*/%!`><v^?_|:\\$.,#gp&~@" X\0\xb2\xb9')
def test_instruction_domains(op):
    for count in range(4):
        for values in itertools.product((-1, 0, 1, 2), repeat=count):
            for heading in range(4):
                check_instruction(op, values, heading=heading, stdin="7 A")


@pytest.mark.parametrize("x", [0, 1, 39, 78, 79])
def test_torus_edges(x):
    for y in (0, 1, 12, 23, 24):
        for op, heading, value in itertools.product("><v^?_|#", range(4), (-1, 0, 1)):
            for choice in range(4) if op == "?" else (0,):
                check_instruction(
                    op, (value,), position=(x, y), heading=heading, choice=choice
                )


@pytest.mark.parametrize("begin", [0, 64, 128, 192])
def test_quoted_bytes_have_no_instruction_effects(begin):
    for value, heading in itertools.product(range(begin, begin + 64), range(4)):
        check_instruction(chr(value), (7,), string=True, heading=heading)


def test_asymmetric_storage_and_byte_normalization():
    for x, y in itertools.product((-1, 0, 1, 2, 79, 80), (-1, 0, 1, 2, 24, 25)):
        check_instruction("g", (x, y), rows=["gAB", "CDE"])
        for value in (-257, -1, 0, 65, 255, 256, 257):
            check_instruction("p", (value, x, y), rows=["pAB", "CDE"])


def test_numeric_and_character_streams():
    base = Reference(["@"])
    lo, hi = base.lower, base.upper
    for stdin in (
        "",
        " ",
        "\n",
        "A",
        "é🙂",
        "-12 7",
        "+23",
        "1_000",
        "\u0660\u0661",
        "x",
        "1__2",
        "+",
        str(lo),
        str(hi),
        str(lo - 1),
        str(hi + 1),
    ):
        for op in "&~":
            check_instruction(op, stdin=stdin)
        for op in "/%":
            check_instruction(op, (3, 0), stdin=stdin)


def test_composed_arithmetic():
    for left, right, op in itertools.product("0123456789", "0123456789", "+-*/%`"):
        check([left + right + op + ".@"], "7")


def test_composed_stack_and_branch_operations():
    for count in range(4):
        for values in itertools.product("012", repeat=count):
            for suffix in (":..@", "\\..@", "$.@", "!.@", "`.@", "_@", "|@", "#9.@"):
                check(["".join(values) + suffix])


def test_published_and_error_controls():
    for command in "~&/%?A":
        for stdin in ("", "7\nZ"):
            check(['"' + command + '".@'], stdin)
    for stdin in ("", "A", "\n", "é🙂", "1 2", "-12 7", "1_000", "x"):
        for code in ("~.@", "&.@", "&&+.@", "~,@"):
            check([code], stdin)
    for code in (
        '"!dlroW ,olleH",,,,,,,,,,,,,@',
        '"A"01p01g,@',
        '"@"40p@',
        "\xb2.@",
        "\xb9.@",
        ">v\n^<",
        "><",
        "<",
        "^",
        ">_@",
    ):
        check(code.splitlines())


@pytest.mark.parametrize("width", [None, 1, 2, 3, 4, 5, 7, 13, 40, 80])
@pytest.mark.parametrize("n", [1, 2, 3])
@pytest.mark.medium
def test_generated_small_tables(n, width):
    for value in range(1 << (1 << n)):
        table = f"{value:0{1 << n}b}"
        program = befunge(table, width)
        for row, answer in enumerate(table):
            ref = check(program.splitlines(), " ".join(f"{row:0{n}b}"), full=False)
            assert ref.done
            assert (ref.output, ref.offset, ref.past_end) == (
                answer + " ",
                2 * n - 1,
                0,
            )


@pytest.mark.parametrize("width", [1, 3, 7, 13, 80])
@pytest.mark.parametrize("n", [4, 5, 6, 8, 10])
@pytest.mark.medium
def test_generated_wider_tables(n, width):
    size = 1 << n
    tables = [
        "0" * size,
        "1" * size,
        "".join(str(row.bit_count() % 2) for row in range(size)),
        "1" + "0" * (size - 1),
        "0" * (size - 1) + "1",
    ]
    if n <= 6:
        rng = random.Random(27183 + n)
        tables.append("".join(str(rng.randrange(2)) for _ in range(size)))
    for table in tables:
        program = befunge(table, width)
        for row, answer in enumerate(table):
            ref = check(program.splitlines(), " ".join(f"{row:0{n}b}"), full=False)
            assert ref.done
            assert (ref.output, ref.offset, ref.past_end) == (
                answer + " ",
                2 * n - 1,
                0,
            )


def test_padded_numeric_input_and_public_run():
    for token, expected in [
        ("0" * 5000 + "17", "17 "),
        ("-" + "\u0660" * 5000 + "\u0661\u0667", "-17 "),
        ("0_" * 5000 + "17", "17 "),
    ]:
        ref = check(["&.@"], token)
        io = ScriptedIO(token)
        run(["&.@"], io)
        assert (ref.output, ref.offset, ref.past_end) == (expected, len(token), 0)
        assert (io.getvalue(), io.position(), io.past_end) == (
            ref.output,
            ref.offset,
            ref.past_end,
        )


def branch_state(ref):
    view = ref.view()
    return view[:4], view[4], view[5], view[6], view[7]


def test_all_draw_graphs_and_branch_purity():
    for kind, expected in [
        ("halt", (True, False)),
        ("mixed", (True, True)),
        ("loop", (False, True)),
    ]:
        rows = [" " * 80 for _ in range(25)]
        rows[0] = "?" + " " * 79
        if kind != "loop":
            rows[0] = "?@" + " " * 77 + "@"
        if kind == "halt":
            rows[1] = "@" + " " * 79
            rows[24] = "@" + " " * 79
        start = Reference(rows)
        states = [start]
        keys = {start.view(): 0}
        edges = []
        index = 0
        machine = _Machine(rows, ScriptedIO(""))
        while index < len(states):
            current = states[index]
            targets = []
            if not current.done:
                at = int(current.position.imag) * 80 + int(current.position.real)
                choices = (
                    range(4)
                    if current.cells[at] == ord("?") and not current.string
                    else (0,)
                )
                actual = machine.branching_successors(branch_state(current), 100)
                assert actual is not None
                for choice in choices:
                    child = copy.deepcopy(current)
                    child.step(choice)
                    assert actual[choice if len(actual) == 4 else 0] == branch_state(
                        child
                    )
                    key = child.view()
                    if key not in keys:
                        keys[key] = len(states)
                        states.append(child)
                    targets.append(keys[key])
            edges.append(targets)
            index += 1
            assert len(states) < 500
        degree = [0] * len(states)
        for targets in edges:
            for target in targets:
                degree[target] += 1
        queue = deque(at for at, value in enumerate(degree) if value == 0)
        removed = 0
        while queue:
            at = queue.popleft()
            removed += 1
            for target in edges[at]:
                degree[target] -= 1
                if degree[target] == 0:
                    queue.append(target)
        can_halt = any(state.done for state in states)
        can_loop = removed < len(states)
        assert (can_halt, can_loop) == expected
    for char in "~&/%?":
        ref = Reference(['"' + char + '"@'], "7")
        live = _Machine(['"' + char + '"@'], ScriptedIO("7"))
        ref.step()
        live.step()
        before = live.snapshot()
        branch = live.branching_successors(live.branching_snapshot(), 100)
        ref.step()
        assert branch == (branch_state(ref),)
        assert live.snapshot() == before
        assert live.io.position() == 0


@pytest.mark.parametrize("rows", [["&\u0100"], ["~🙂"]])
def test_nonbyte_source_is_rejected_before_effects(rows):
    io = ScriptedIO("7A")
    with pytest.raises(ValueError, match="byte"):
        Reference(rows)
    with pytest.raises(ValueError, match="byte"):
        _Machine(rows, io)
    assert io.position() == 0
    assert io.getvalue() == ""


def test_completed_state_has_no_read_or_random_effects():
    ref = Reference(["@~&?"], "7A")
    io = ScriptedIO(ref.stdin)
    draws = Draws(0)
    machine = _Machine(["@~&?"], io, draws)
    ref.step()
    machine.step()
    before = machine.snapshot()
    ref.step()
    machine.step()
    assert machine.snapshot() == before == ref.view()
    state = machine.branching_snapshot()
    assert state == branch_state(ref)
    assert _advance(state) == (state, None)
    assert machine.branching_halted(state)
    assert machine.branching_successors(state, 100) == (state,)
    assert (io.getvalue(), io.position(), draws.calls) == ("", 0, [])


def test_branching_refuses_every_actual_read():
    for command, values, quoted in itertools.product(
        "&~/%", [(), (3, 0), (3, 1)], [False, True]
    ):
        ref = Reference([command], "7")
        ref.values = values
        ref.string = quoted
        io = ScriptedIO(ref.stdin)
        machine = _Machine([command], io)
        machine.state = (
            machine.state[0],
            machine.state[1],
            list(values),
            quoted,
            False,
        )
        before = machine.snapshot()
        ref.step()
        successor = machine.branching_successors(machine.branching_snapshot(), 100)
        if ref.offset:
            assert successor is None
        else:
            assert successor == (branch_state(ref),)
        assert machine.snapshot() == before
        assert io.position() == 0
        machine.step()
        assert machine.snapshot() == ref.view()


@pytest.mark.parametrize("n", range(1, 11))
@pytest.mark.parametrize("width", [None, 4, 5, 11, 27, 81, 1000])
@pytest.mark.medium
def test_public_generator_and_balance_execute_independently(n, width):
    rng = random.Random(n)
    table = "".join(str(rng.randrange(2)) for _ in range(1 << n))
    program = esolangs.generate("Befunge", table, width)
    for row, answer in enumerate(table):
        bits = [int(bit) for bit in f"{row:0{n}b}"]
        stdin = esolangs.encode_inputs("Befunge", bits)
        ref = check(program.splitlines(), stdin, full=False)
        assert ref.done
        assert (ref.output, ref.offset, ref.past_end) == (
            answer + " ",
            len(stdin.rstrip()),
            0,
        )
