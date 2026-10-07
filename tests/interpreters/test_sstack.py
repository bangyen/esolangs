"""Tests for the SStack interpreter."""

import re

import pytest

from esolangs.exceptions import HaltError
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.sstack import _Machine, run


def _out(code: str, stdin: str = "") -> str:
    io = ScriptedIO(stdin)
    run(code, io)
    return io.getvalue()


def test_push_and_print_peek() -> None:
    assert _out('"72/a":a:"105/g":g::g:') == "Hii"


def test_move_increment_decrement_are_pops() -> None:
    # 65 moves a->b, b->c incremented, c->d decremented; a, b, c end empty.
    assert _out('"65/a">a/b<+b/c+-c/d-:d::a::b::c:') == "A\0\0\0"
    assert _out('"7/a"+a/a+-a/a--a/a-:a:') == "\6"


def test_empty_stack_reads_zero_and_decrement_of_zero_is_a_nop() -> None:
    io = ScriptedIO()
    machine = _Machine("-a/b-+c/d+>e/f<~g~", io)
    while not machine.halted:
        machine.step()
    assert machine.stacks == {
        "a": [],
        "b": [0],
        "c": [],
        "d": [1],
        "e": [],
        "f": [0],
        "g": [],
    }


def test_pop_exposes_the_value_below() -> None:
    assert _out('"66/a""67/a"~a~:a:') == "B"


def test_input_pushes_bytes_and_eof_raises() -> None:
    assert _out(";a;;b;:b::a:", "xy") == "yx"
    with pytest.raises(EOFError):
        _out(";a;", "")


def test_loop_runs_while_tops_are_equal_and_retests() -> None:
    # Counts a down from 3 printing 'A' each lap; leaves when e gets a 1.
    loop = '"3/a"[d\\e/"65/f":f:~f~-a/a-[a\\b/"1/e""9/a"]]'
    assert _out(loop) == "AAA"


def test_loop_skips_when_tops_differ() -> None:
    assert _out('"1/a"[a\\b/"88/c":c:]"89/c":c:') == "Y"


def test_print_above_a_byte_raises() -> None:
    assert _out('"255/a":a:') == "\xff"
    with pytest.raises(HaltError):
        _out('"256/a":a:')


def test_whitespace_is_discarded_inside_tokens() -> None:
    assert _out(' "6\n5 / a"\n:\ta:') == "A"


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("x", "position 0"),
        ('"1/a" >a/b+', "position 6"),  # mismatched closer
        (";a:", "position 0"),
        ('"1/h"', "position 0"),  # no stack h
        ("!", "position 0"),  # the page's input separator
        ("  [a\\b/", "unmatched '[' at position 2"),
        (' "1/a"]', "unmatched ']' at position 6"),
    ],
)
def test_malformed_source_is_rejected_at_its_original_position(
    code: str, message: str
) -> None:
    with pytest.raises(ValueError, match=re.escape(message)):
        _out(code)


def test_snapshot_carries_the_input_cursor() -> None:
    machine = _Machine(";a;~a~", ScriptedIO("z"))
    start = machine.snapshot()
    machine.step()
    machine.step()
    assert machine.halted
    # Same stacks as at the start; only the cursor and the input moved.
    assert machine.snapshot()[1] == start[1]
    assert machine.snapshot()[2] != start[2]
