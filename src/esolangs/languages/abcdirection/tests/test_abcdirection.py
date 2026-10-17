"""Tests for the ABCDirection interpreter."""

import pytest

from esolangs.languages.abcdirection.interpreter import (
    DOWN,
    LEFT,
    RIGHT,
    UP,
    _advance,
    _Effect,
    _Machine,
    _State,
    run,
)
from esolangs.runtime.io import ScriptedIO


def output(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


#: Eight C's down column 0 print a zero byte; the D row then turns the
#: pointer left (zero cell, empty queue), where dequeueing nothing repeats.
ZERO_BYTE = "\n".join(["CBBBBB"] * 8 + ["DDDDDD"])


@pytest.mark.parametrize(
    ("command", "heading", "here", "right", "queue", "read", "after", "effect"),
    [
        ("A", UP, 0, 0, (0, 0), None, (RIGHT, 5), _Effect()),
        ("B", LEFT, 1, 0, (0, 0), None, (LEFT, 5), _Effect()),
        ("C", RIGHT, 0, 0, (0, 0), None, (RIGHT, 4), _Effect()),
        ("C", LEFT, 0, 1, (0, 0), None, (LEFT, 6), _Effect(write=(6, 0))),
        ("C", UP, 1, 0, (0, 0), None, (LEFT, 5), _Effect()),
        ("C", UP, 0, 0, (0, 0), None, (UP, 5), _Effect()),
        ("C", DOWN, 1, 0, (0, 0), None, (DOWN, 5), _Effect(emit=1)),
        ("D", RIGHT, 1, 0, (0, 0), None, (RIGHT, 5), _Effect(push=1)),
        ("D", LEFT, 0, 0, (1, 0), None, (LEFT, 5), _Effect(write=(5, 1), pops=1)),
        ("D", UP, 0, 0, (0, 0), 1, (UP, 5), _Effect(write=(5, 1))),
        ("D", DOWN, 1, 0, (1, 1), None, (DOWN, 5), _Effect()),
        ("D", DOWN, 0, 0, (1, 0), None, (UP, 5), _Effect(pops=1)),
        ("D", DOWN, 0, 0, (0, 1), None, (RIGHT, 5), _Effect(pops=2)),
        ("D", DOWN, 0, 0, (0, 0), None, (LEFT, 5), _Effect(pops=2)),
    ],
)
def test_each_command_by_heading(
    command, heading, here, right, queue, read, after, effect
):
    """The spec's table; a D down dequeues the bit it tests."""
    grid = ("B" + command + "B",) * 3
    state, got = _advance(_State(1, 1, heading, 5), grid, here, right, queue, read)
    assert (state.heading, state.cell) == after
    assert got == effect


def test_the_pointer_wraps_around_the_grid():
    state, _ = _advance(_State(0, 0, LEFT, 0), ("BB", "BB"), 0, 0, (0, 0), None)
    assert (state.x, state.y) == (1, 0)


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("BBBBBB\nBBBBBB", "DDDDDD"),
        ("CBBBBB\nCBBBBX\nDDDDDD", "A, B, C, D"),
        ("CBBBBB\nCBBBB\nDDDDDD", "rectangle"),
        # The terminator's line is read whole, so it sets the width.
        ("CBBBBB\nDDDDDDB", "rectangle"),
    ],
)
def test_a_malformed_grid_is_refused(code: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        output(code)


def test_lines_after_the_terminator_are_a_comment() -> None:
    assert output(ZERO_BYTE + "\nanything, even DDDDDD again") == "\x00"


def test_a_column_of_outputs_prints_a_byte_then_halts_in_silence() -> None:
    assert output(ZERO_BYTE) == "\x00"
    assert output("\n".join(["CBBBBB"] * 16 + ["DDDDDD"])) == "\x00\x00"


def test_reads_past_eof_supply_zeros() -> None:
    """The pointer laps a read until the input is spent, then repeats."""
    assert output("ABBBBB\nDDDDDD", "A") == ""
    assert output("ABBBBB\nDDDDDD") == ""


def test_a_program_that_keeps_printing_never_halts() -> None:
    machine = _Machine("CBBBBBB\nCDDDDDD", ScriptedIO())
    for _ in range(800):
        machine.step()
    assert not machine.halted
    assert machine.io.getvalue() == "\x00" * 100


def test_a_step_after_the_halt_changes_nothing() -> None:
    machine = _Machine("DDDDDD", ScriptedIO())
    while not machine.halted:
        machine.step()
    before = machine.snapshot()
    machine.step()
    assert machine.snapshot() == before


def test_memory_spans_the_highest_one() -> None:
    """``A`` heads the pointer left onto the wrapped ``C``, which sets cell 1."""
    machine = _Machine("ABBBBC\nDDDDDD", ScriptedIO())
    machine.step()
    machine.step()
    assert machine.memory == [0, 1]


def test_snapshots_tell_tapes_apart_down_to_the_last_one() -> None:
    blank = _Machine("DDDDDD", ScriptedIO())
    marked = _Machine("DDDDDD", ScriptedIO())
    marked.ones.add(0)
    assert blank.snapshot() != marked.snapshot()


def test_input_characters_wrap_to_a_byte() -> None:
    """A read lays its byte onto the tape; chr(300) is chr(44)."""

    def tape(stdin: str) -> tuple[list[int], int]:
        machine = _Machine("AAAAAC\nDDDDDD", ScriptedIO(stdin))
        for _ in range(400):
            machine.step()
        return machine.memory, machine.writes

    assert tape("\u012c") == tape(",")
