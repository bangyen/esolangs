"""Tests for the NOR machine interpreter."""

import pytest

from esolangs.languages.nor_machine.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.runner import native_runner

_out = native_runner(run)


def test_lone_nor_prints_the_value_itself() -> None:
    assert _out("V", "5") == "5"


@pytest.mark.parametrize("part", [0, 1])
def test_nor_is_twos_complement(part) -> None:
    from esolangs.languages.nor_machine.tests.oracle_checks import (
        check_raw_nor_machine,
    )

    check_raw_nor_machine(part)
    # ~(5 | 2) = -8.
    assert _out("V V", "5 2") == "-8"


def test_shifts_floor_on_negatives() -> None:
    assert _out("R V", "-1") == "-1"
    assert _out("L V", "-3") == "-6"


def test_swap_and_rotate_reorder_the_queue() -> None:
    # 4 3 -> X -> 3 4 -> L -> 4 6 -> R -> 6 2 -> V prints ~(6 | 2) = -7.
    assert _out("XLRVV", "4 3") == "-7"
    # 8 1 -> I -> 1 8 -> R -> 8 0 -> V prints ~(8 | 0) = -9.
    assert _out("IRVV", "8 1") == "-9"


def test_dup_enqueues_twice() -> None:
    # 3 -> 3 3 -> ~(3 | 3) = -4.
    assert _out("AVV", "3") == "-4"


def test_program_repeats_until_a_lone_nor() -> None:
    # L doubles the value each pass, then V ends the first pass on one value.
    assert _out("L V", "1") == "2"
    io = ScriptedIO("1 2")
    machine = _Machine("L", io)
    for _ in range(50):
        machine.step()
    assert not machine.halted


def test_whitespace_is_skipped_and_bad_source_is_rejected(monkeypatch) -> None:
    assert _out(" L\n V ", "3") == "6"
    with pytest.raises(ValueError, match="unknown command"):
        _out("Lx", "1")
    with pytest.raises(ValueError, match="no command"):
        _out(" ")

    from esolangs.languages.nor_machine import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "NOR machine",
        " L V ",
        interpreter,
        "_parse",
        monkeypatch,
        cases=(("1", "2"), ("3", "6"), ("-1", "-2")),
    )
