"""Ant transitions and exact generated cycles checked by a white-set model."""

import itertools
import random
from collections.abc import MutableMapping
from unittest.mock import patch

import pytest

from esolangs.interpreters.grid_based.a_painter_ant import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from esolangs.tools.a_painter_ant import a_painter_ant
from esolangs.tools.helpers import TEMPLATE_CHAR
from tests.interpreters.a_painter_ant_reference import Reference
from tests.interpreters.views import view as vm_view


class ObservedGrid(MutableMapping):
    def __init__(self, values=()):
        self.cells = dict(values)
        self.writes = []

    def __getitem__(self, key):
        return self.cells[key]

    def __iter__(self):
        return iter(self.cells)

    def __len__(self):
        return len(self.cells)

    def get(self, key, default=None):
        return self.cells.get(key, default)

    def __setitem__(self, key, value):
        self.writes.append((key, value))
        self.cells[key] = value

    def __delitem__(self, key):
        self.writes.append(("delete", key))
        del self.cells[key]


def view(position):
    return int(position.real), -int(position.imag)


def pair(code):
    reference = Reference(code)
    io = ScriptedIO("unused")
    native = _Machine(code, io)
    grid = ObservedGrid()
    native.grid = grid
    return native, reference, grid, io


def transition(native, reference, grid, io):
    command = reference.source[reference.cursor] if reference.source else ""
    expected = (
        [(view(reference.position), int(command == "P"))]
        if command in ("p", "P")
        else []
    )
    grid.writes.clear()
    reference.step()
    native.step()
    assert native.grid is grid
    assert grid.writes == expected
    assert (native.x, native.y, vm_view(native, "ip")) == (
        *view(reference.position),
        reference.cursor,
    )
    assert native.halted is False
    assert (io.getvalue(), io.position(), io.past_end) == ("", 0, 0)


def boundary(native, reference):
    assert native.snapshot() == reference.native_view()
    assert native.visited == {view(p) for p in reference.visited}
    assert native.render() == reference.render()
    assert vm_view(native, "memory") == [
        value for _, value in sorted(dict(reference.native_view()[0]).items())
    ]
    assert vm_view(native, "stack") == []


@pytest.mark.parametrize("command", "nNeEsSwWpP")
@pytest.mark.parametrize("origin", [0j, 7 - 11j])
def test_all_neighbourhoods(command, origin):
    cells = [complex(x, y) + origin for y in range(-1, 2) for x in range(-1, 2)]
    for mask in range(512):
        native, reference, grid, io = pair(command)
        reference.position = origin
        reference.visited = {origin}
        reference.painted = set(cells)
        reference.white = {p for i, p in enumerate(cells) if mask >> i & 1}
        native.x, native.y = view(origin)
        native.visited = {view(origin)}
        grid.update({view(p): int(p in reference.white) for p in cells})
        transition(native, reference, grid, io)
        boundary(native, reference)


@pytest.mark.medium
@pytest.mark.parametrize("first", "nNeEsSwWpP")
def test_all_short_programs(first):
    for length in range(1, 5):
        for tail in itertools.product("nNeEsSwWpP", repeat=length - 1):
            code = first + "".join(tail)
            native, reference, grid, io = pair(code)
            saved = []
            for _ in range(4):
                for _ in code:
                    transition(native, reference, grid, io)
                    saved.append((native.snapshot(), reference.native_view()))
                boundary(native, reference)
            assert all(
                actual == expected and hash(actual) == hash(expected)
                for actual, expected in saved
            )


@pytest.mark.medium
@pytest.mark.parametrize("seed", range(8))
def test_long_walks(seed):
    rng = random.Random(781 + seed)
    for _ in range(16):
        code = "".join(rng.choice("nNeEsSwWpP") for _ in range(80))
        native, reference, grid, io = pair(code)
        for _ in range(12):
            for _ in code:
                transition(native, reference, grid, io)
            boundary(native, reference)


@pytest.mark.parametrize("code", ["", "N", "NESW", "p", "P", "NPsP", "PnpS", "nesw"])
def test_run_and_interrupt_after_exact_repeat(code):
    native, reference, grid, io = pair(code)
    seen = {reference.storage_state(): native.snapshot()}
    for _ in range(64):
        for _ in reference.source:
            transition(native, reference, grid, io)
        boundary(native, reference)
        state = reference.storage_state()
        if state in seen:
            assert native.snapshot() == seen[state]
            break
        seen[state] = native.snapshot()
    else:
        pytest.fail("execution bound reached without cycle certificate")
    from esolangs.vm import run_until_halt_or_cycle

    assert run_until_halt_or_cycle(_Machine(code)) is False
    expected = reference.render()
    native.interrupt()
    snapshot = native.snapshot()
    native.step()
    native.step()
    assert io.getvalue() == expected
    assert native.snapshot() == snapshot
    public = ScriptedIO("unused")
    original = _Machine.step
    calls = 0

    def guarded(machine):
        nonlocal calls
        calls += 1
        if calls > 128 * max(1, len(reference.source)):
            pytest.fail("execution bound reached in public runner")
        return original(machine)

    with patch.object(_Machine, "step", guarded):
        run(code, public)
    assert public.getvalue() == expected
    assert (public.position(), public.past_end) == (0, 0)


@pytest.mark.parametrize(
    "white", [" ", "\t", "\n", "\r", "\v", "\f", "\u00a0", "\u2003", "\u2028"]
)
def test_whitespace_does_not_occupy_a_cursor(white):
    code = white.join("nPsNp")
    native, reference, grid, io = pair(code)
    assert native.prog == reference.source
    for _ in range(20):
        transition(native, reference, grid, io)
        boundary(native, reference)


@pytest.mark.parametrize("bad", ["x", "0", "#", "\u2115", "\uff2e", "\u017f", "\u200b"])
def test_invalid_instructions_never_execute(bad):
    io = ScriptedIO()
    with pytest.raises(ValueError, match="unknown instruction"):
        _Machine("P" + bad, io)
    with pytest.raises(ValueError, match="invalid instruction"):
        Reference("P" + bad)
    assert io.getvalue() == ""


def instantiate(table, row):
    n = len(table).bit_length() - 1
    pieces = a_painter_ant(table).split(TEMPLATE_CHAR)
    assert len(pieces) == n + 1
    return pieces[0] + "".join(
        ("N" if row >> (n - 1 - i) & 1 else "n") + pieces[i + 1] for i in range(n)
    )


def generated(table, row):
    code = instantiate(table, row)
    native, reference, grid, io = pair(code)
    seen = {reference.storage_state(): native.snapshot()}
    for _ in range(4):
        for _ in code:
            transition(native, reference, grid, io)
        boundary(native, reference)
        assert int(reference.position in reference.white) == int(table[row])
        state = reference.storage_state()
        if state in seen:
            assert native.snapshot() == seen[state]
            return len(code)
        seen[state] = native.snapshot()
    pytest.fail("execution bound reached without generated cycle certificate")


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "start"),
    [(n, start) for n in (1, 2, 3) for start in range(0, 1 << (1 << n), 16)],
)
def test_generated_small_tables(n, start):
    for value in range(start, min(start + 16, 1 << (1 << n))):
        table = format(value, f"0{1 << n}b")
        for row in range(1 << n):
            generated(table, row)


def wider_table(n, shape):
    size = 1 << n
    if shape == "zero":
        return "0" * size
    if shape == "one":
        return "1" * size
    if shape == "first":
        return "1" + "0" * (size - 1)
    if shape == "last":
        return "0" * (size - 1) + "1"
    if shape == "parity":
        return "".join(str(row.bit_count() % 2) for row in range(size))
    rng = random.Random(901 + n)
    return "".join(rng.choice("01") for _ in range(size))


def wider_rows(n):
    size = 1 << n
    if n <= 6:
        return list(range(size))
    return sorted(
        {
            0,
            1,
            size // 2 - 1,
            size // 2,
            size - 2,
            size - 1,
            *[1 << i for i in range(n)],
            *[size - 1 - (1 << i) for i in range(n)],
        }
    )


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "shape", "start"),
    [
        (n, shape, start)
        for n in range(4, 11)
        for shape in ("zero", "one", "first", "last", "parity", "random")
        for start in range(0, len(wider_rows(n)), 2)
    ],
)
def test_generated_wider_tables(n, shape, start):
    table = wider_table(n, shape)
    for row in wider_rows(n)[start : start + 2]:
        generated(table, row)


COUNTER = """\
PePePePePePePePePePePePePePePePePePePePePePePePePePe
PEpW
ePWsPN
EpWSpN
WsPN
ESpNWePW
sss
        ePwPsPN"""


@pytest.mark.medium
@pytest.mark.parametrize(("code", "passes"), [("PnPwPsPe", 3), (COUNTER, 2000)])
def test_published_growing_walks(code, passes):
    native, reference, grid, io = pair(code)
    for _ in range(passes):
        for _ in reference.source:
            transition(native, reference, grid, io)
    boundary(native, reference)
    if passes == 3:
        assert native.render() == ".##\n###\n##.\n.#o"
    else:
        rows = native.render().splitlines()
        assert len(rows) == 5927
        assert {len(row) for row in rows} == {28}
        assert rows[-2:] == [
            "@#..........................",
            "#...........................",
        ]


@pytest.mark.parametrize("seed", range(8))
def test_trace_helper_against_reference(seed):
    from tests.tools import a_painter_ant_trace as trace

    rng = random.Random(2041 + seed)
    code = "".join(rng.choice("nNeEsSwWpP") for _ in range(24))
    reference = Reference(code)
    expected = []
    landings = []
    for _ in range(3):
        for cursor, command in enumerate(code):
            previous = reference.position
            target = (
                previous + {"n": 1j, "e": 1, "s": -1j, "w": -1}[command.lower()]
                if command not in "pP"
                else None
            )
            reference.step()
            action = (
                ("paint_white" if command == "P" else "paint_black")
                if target is None
                else ("moved" if reference.position != previous else "blocked")
            )
            expected.append(
                (
                    cursor,
                    command,
                    view(reference.position),
                    action,
                    None if target is None else view(target),
                )
            )
        landings.append(view(reference.position))
    actual = trace.run(code, 3)
    assert [
        (step.index, step.command, step.position, step.action, step.target)
        for step in actual.steps
    ] == expected
    assert actual.grid == dict(reference.native_view()[0])
    assert actual.visited == {view(p) for p in reference.visited}
    assert actual.position == view(reference.position)
    assert actual.landings == landings
    assert trace.box(code, 3) == reference.render()
    assert actual.landing_colour() == int(reference.position in reference.white)


@pytest.mark.parametrize("width", [None, 1, 9, 100])
def test_public_generation_instantiation_and_answer(width):
    import esolangs

    for table in ("0000", "1111", "0110", "0010", "0100", "1000"):
        template = esolangs.generate("A Painter Ant", table, width=width)
        for row in range(4):
            bits = [row >> 1, row & 1]
            code = esolangs.instantiate("A Painter Ant", template, bits)
            reference = Reference(code)
            seen = {reference.storage_state()}
            for _ in range(4):
                for _ in reference.source:
                    reference.step()
                state = reference.storage_state()
                if state in seen:
                    break
                seen.add(state)
            else:
                pytest.fail("execution bound reached in public template")
            assert int(reference.position in reference.white) == int(table[row])
            output = esolangs.run("A Painter Ant", code, timeout=1)
            assert output == reference.render()
            assert esolangs.read_answer("A Painter Ant", output) == table[row]
