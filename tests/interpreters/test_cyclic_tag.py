"""Cyclic tag execution and source conventions."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.queue_based.cyclic_tag import _Machine, run
from esolangs.tools.cyclic_tag import cyclic_tag
from esolangs.tools.helpers import TEMPLATE_CHAR, essential_inputs, fill_runs
from tests.raises import assert_rejected_with_hint
from tests.witness_tables import witnesses


def test_all_three_input_tables() -> None:
    for n in range(1, 4):
        for table in witnesses(n):
            template = cyclic_tag(table)
            # Exact when every input matters; an ignored one's rule is empty.
            bound = 5 * len(table) + 2 * n + 1
            ignores = len(essential_inputs(table, n)) < n
            assert len(template) < bound if ignores else len(template) == bound
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
