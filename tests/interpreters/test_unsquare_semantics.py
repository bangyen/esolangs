"""Independent Unsquare primitives, loops, ports and bounded programs."""

import random

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.unsquare import _Machine
from esolangs.vm import run_until_halt_or_cycle
from tests.interpreters.unsquare_observer import check, compare, step
from tests.interpreters.unsquare_reference import Reference


@pytest.mark.parametrize("op", "OIAS+-xPoi?")
@pytest.mark.parametrize("accumulator", [-2, 0, 1, 2, 2**80])
def test_command_rule(op, accumulator):
    for values in [(), (0,), (1, 65), (-4294967296, 0xD800, 0x110000)]:
        ref = Reference(op, "λ")
        ref.accumulator = accumulator
        ref.values = list(values)
        port = ScriptedIO("λ")
        machine = _Machine(op, port)
        machine.state = (0, accumulator, values, ())
        step(machine, ref, port)


@pytest.mark.parametrize(
    "value",
    [
        -4294967296,
        -2,
        -1,
        0,
        1,
        0xD7FF,
        0xD800,
        0xDFFF,
        0xE000,
        0x10FFFF,
        0x110000,
        4294967361,
        2**80,
    ],
)
def test_output_profile_and_nonpop(value):
    ref = Reference("o")
    ref.values = [value]
    port = ScriptedIO()
    machine = _Machine("o", port)
    machine.load((value,))
    assert step(machine, ref, port) is None
    assert machine.stack == (value,)


@pytest.mark.parametrize(
    ("program", "pc", "opens"),
    [
        (">--<", 0, []),
        (">--<", 3, [0]),
        (">>--<<", 1, [0]),
        (">>--<<", 4, [0, 1]),
        (">>--<<", 5, [0]),
        (">", 0, []),
        (">>", 0, []),
        ("<", 0, []),
    ],
)
@pytest.mark.parametrize("accumulator", [-2, 0, 1, 2, 2**80])
def test_loop_rule(program, pc, opens, accumulator):
    ref = Reference(program)
    ref.pc = pc
    ref.accumulator = accumulator
    ref.loops = list(opens)
    port = ScriptedIO()
    machine = _Machine(program, port)
    machine.state = (pc, accumulator, (), tuple(start - 1 for start in opens))
    step(machine, ref, port)


@pytest.mark.parametrize("shard", range(12))
def test_bounded_programs(shard):
    rng = random.Random(67140)

    def source(depth):
        parts = []
        for _ in range(rng.randrange(1, 5)):
            parts.append(
                ">" + source(depth - 1) + "<"
                if depth and rng.randrange(4) == 0
                else rng.choice("OIAS+-xPoi ?")
            )
        return "".join(parts)

    for case in range(1200):
        program = source(3)
        if case % 12 != shard:
            continue
        text = "A\nλ\0\1" * 8
        ref = Reference(program, text)
        port = ScriptedIO(text)
        machine = _Machine(program, port)
        for _ in range(80):
            compare(machine, ref, port)
            if ref.halted or step(machine, ref, port):
                break


@pytest.mark.parametrize("text", ["", " ", "\n", "λ🙂", "A\0B"])
def test_unicode_stream_and_eof(text):
    result = check("io" * (len(text) + 1), text)
    assert result["reads"] == len(text)
    assert result["error"] == "EOFError"


def test_cursorless_input_progress():
    class Cursorless(ScriptedIO):
        def position(self):
            return None

    port = Cursorless("\2" * 8)
    machine = _Machine("++>iA+<", port)
    with pytest.raises(EOFError):
        run_until_halt_or_cycle(machine, 200)
    assert port.reads == 8


def test_static_programs_have_distinct_snapshots():
    assert (
        _Machine("O", ScriptedIO()).snapshot() != _Machine("I", ScriptedIO()).snapshot()
    )


@pytest.mark.parametrize("accumulator", [0, 1, 2, -2])
def test_unmatched_opening_loop_is_halted_error(accumulator):
    machine = _Machine(">", ScriptedIO())
    machine.state = (0, accumulator, (), ())
    with pytest.raises(HaltError, match="unmatched >"):
        machine.step()
    assert machine.halted
