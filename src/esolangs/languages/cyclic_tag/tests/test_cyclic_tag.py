"""Cyclic tag execution and source conventions."""

import pytest

from esolangs.generation.helpers import TEMPLATE_CHAR, essential_inputs, fill_runs
from esolangs.languages.cyclic_tag.generator import cyclic_tag
from esolangs.languages.cyclic_tag.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO
from tests.support.raises import assert_rejected_with_hint
from tests.support.witness_tables import witnesses


def test_all_three_input_tables() -> None:
    for n in range(1, 4):
        for table in witnesses(n):
            template = cyclic_tag(table)
            # limitations.md: 5 * 2**m + 2n + 1 for m essential inputs, else
            # n + 2 for a constant; an ignored input's rule is empty.
            m = len(essential_inputs(table, n))
            size = n + 2 if len(set(table)) == 1 else 5 * 2**m + 2 * n + 1
            assert len(template) == size, table
            for row in range(1 << n):
                bits = [int(c) for c in f"{row:0{n}b}"]
                code = fill_runs(template, TEMPLATE_CHAR, (("0", "1"),) * n, bits)
                io = ScriptedIO()
                run(code, io)
                assert io.getvalue() == table[row]


@pytest.mark.parametrize("code", ["", "1", "1,,0", "x,1", "1,0;1"])
def test_invalid_source(code: str) -> None:
    with pytest.raises(ValueError, match="Cyclic tag"):
        run(code, ScriptedIO())


def test_empty_rule_and_queue() -> None:
    io = ScriptedIO()
    run(" , 1 ", io)
    assert io.getvalue() == "1"
    empty = ScriptedIO()
    run("1;0,", empty)
    assert empty.getvalue() == ""


def test_queue_transition_and_cyclic_schedule() -> None:
    machine = _Machine("11;0,10", ScriptedIO())
    machine.step()
    assert machine.live == "011"
    assert machine.head == 1
    machine.step()
    assert machine.live == "11"
    assert machine.head == 0


def test_source_offsets_and_cycle_snapshot() -> None:
    machine = _Machine(" 1; 1,1", ScriptedIO())
    assert machine.ip == 1
    machine.step()
    assert machine.ip == 4
    before = machine.snapshot()
    machine.step()
    machine.step()
    assert machine.snapshot() == before
    assert not machine.halted


def test_the_wiki_evolution() -> None:
    """Productions (011, 10, 101) on data 1, as tabulated at oldid 156412."""
    machine = _Machine("011;10;101,1", ScriptedIO())
    trace = []
    for _ in range(7):
        trace.append(machine.live)
        machine.step()
    assert trace == ["1", "011", "11", "1101", "101011", "0101110", "101110"]


@pytest.mark.medium
def test_malformed_source_carries_a_repair_hint() -> None:
    assert_rejected_with_hint("Cyclic tag", "0,1;", "semicolons only before")
