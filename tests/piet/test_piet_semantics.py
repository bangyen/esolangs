"""Piet comparisons against independent command and raster models."""

import itertools

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.piet import _advance, _command, _Machine
from esolangs.raster import Raster
from esolangs.tools.piet import piet
from tests.interpreters.views import view as vm_view
from tests.piet.piet_cases import raster_case, stacks
from tests.piet.piet_commands import command
from tests.piet.piet_raster import BLACK, advance
from tests.piet.piet_reference import Reference
from tests.piet.piet_scale import normalize

NAMES = {
    "read_num": "number",
    "read_char": "char",
    "write_num": "out_number",
    "write_char": "out_char",
}


def normalized_result(result):
    values, dp, cc, effect = result
    if effect:
        effect = (NAMES.get(effect[0], effect[0]), effect[1])
    return (values, dp % 4, cc % 2, effect)


@pytest.mark.parametrize("shard", range(64))
def test_command_arithmetic(shard):
    for stack in stacks()[shard::64]:
        for change in itertools.product(range(6), range(3)):
            for size in (1, 3, 7):
                assert normalized_result(
                    _command(change, size, stack)
                ) == normalized_result(command(change, size, stack))


@pytest.mark.parametrize("shard", range(20))
def test_raster_transitions(shard):
    for seed in range(shard * 100, (shard + 1) * 100):
        rows, point, stack = raster_case(seed)
        for dp, cc in itertools.product(range(4), (-1, 1)):
            state = (point, dp, cc, stack, rows[point[1]][point[0]] == BLACK)
            expected = advance(state, rows)
            actual, effect = _advance(state, rows)
            if effect:
                effect = (NAMES[effect[0]], effect[1])
            assert expected == (actual, effect)


def compare_execution(program, text, requested, limit=100):
    rows, _ = normalize(program.rows, requested)
    ref = Reference(rows, text)
    io = ScriptedIO(text)
    vm = _Machine(program, io, scale=requested)
    key = (len(rows[0]), len(rows), bytes(c for row in rows for p in row for c in p))
    for generation in range(limit + 1):
        assert vm.state == ref.state
        assert vm.snapshot() == (
            *ref.state[:4],
            ref.position,
            ref.state[4],
            key,
            ref.reads,
        )
        assert (io.position(), io.reads, io.getvalue()) == (
            ref.position,
            ref.reads,
            ref.output,
        )
        assert vm_view(vm, "ip") == (
            None
            if ref.state[4]
            else (ref.state[0][1], ref.state[0][0], ref.state[1], ref.state[2])
        )
        assert vm_view(vm, "memory") == []
        if ref.state[4]:
            return ref
        if generation == limit:
            return ref
        snap = vm.snapshot()
        hashed = hash(snap)
        ref.step()
        vm.step()
        assert hash(snap) == hashed
    raise AssertionError("unreachable bound")


@pytest.mark.parametrize("shard", range(40))
def test_full_random_execution(shard):
    for seed in range(shard * 50, (shard + 1) * 50):
        rows, text = raster_case(seed, execution=True)
        compare_execution(Raster(rows), text, 1)


@pytest.mark.parametrize(
    ("n", "number", "width", "scale"),
    [
        (n, number, width, scale)
        for n in range(1, 4)
        for number in range(1 << (1 << n))
        for width in (None, 20, 40)
        for scale in (1, 2, 3)
    ],
)
def test_generated_png_scale(n, number, width, scale):
    table = format(number, f"0{1 << n}b")
    base = piet(table, width)
    image = base.upscaled(scale)
    decoded = Raster.from_png(image.to_png())
    assert image.rows == decoded.rows
    rows, factor = normalize(decoded.rows)
    assert rows == base.rows
    assert factor == scale
    for requested in (None, scale):
        for row, answer in enumerate(table):
            result = compare_execution(
                decoded, " ".join(format(row, f"0{n}b")), requested, 10000
            )
            assert result.state[4]
            assert result.output == answer
            assert result.reads == n


def test_cursorless_input_progress():

    class Cursorless(ScriptedIO):
        def position(self):
            return 0

    program = Raster((((255, 192, 192), (0, 0, 192)),))
    io = Cursorless("bad bad bad bad")
    vm = _Machine(program, io, scale=1)
    seen = set()
    for _generation in range(100):
        snap = vm.snapshot()
        if snap in seen:
            break
        seen.add(snap)
        vm.step()
    else:
        raise AssertionError("no terminal input cycle")
    assert io.reads == 4


def test_program_identity():
    red = (255, 192, 192)
    a = _Machine(Raster(((red, (255, 0, 0)),)), ScriptedIO(""), scale=1)
    b = _Machine(Raster(((red, (255, 255, 192)),)), ScriptedIO(""), scale=1)
    assert a.snapshot() != b.snapshot()
    a.step()
    b.step()
    assert a.stack == (1,)
    assert b.stack == ()


@pytest.mark.medium
@pytest.mark.parametrize(
    ("index", "balanced"),
    [(index, balanced) for index in range(54) for balanced in (False, True)],
)
def test_legacy_public_generation(index, balanced):
    import esolangs
    from tests.piet.piet_cases import legacy_tables

    n, table = legacy_tables()[index]
    program = esolangs.generate("Piet", table, balance=balanced)
    decoded = Raster.from_png(program.to_png())
    assert decoded.rows == program.rows
    for row, answer in enumerate(table):
        result = compare_execution(
            decoded, " ".join(format(row, f"0{n}b")), None, 10000
        )
        assert result.state[4]
        assert result.output == answer
        assert result.reads == n


@pytest.mark.parametrize("text", ["Z", "\n", "\x00", "ā", "λ🙂"])
@pytest.mark.parametrize("scale", [1, 3])
def test_character_io(text, scale):
    red = (255, 192, 192)
    black = (0, 0, 0)
    blue = (0, 0, 192)
    magenta = (255, 192, 255)
    program = Raster(
        (
            (red, black, black, blue),
            (red, red, magenta, blue),
            (black, black, black, blue),
        )
    ).upscaled(scale)
    result = compare_execution(Raster.from_png(program.to_png()), text, None)
    assert result.state[4]
    assert result.output == text[0]
