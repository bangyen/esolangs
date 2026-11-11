"""Cyclic tag execution and source conventions."""

import pytest

from esolangs._bindings import TEMPLATE_CHAR, fill_runs
from esolangs.generation.helpers import essential_inputs, read_at
from esolangs.languages.cyclic_tag.generator import cyclic_tag
from esolangs.languages.cyclic_tag.interpreter import _execute, _Machine, run
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime.io import ScriptedIO
from tests.support.raises import assert_rejected_with_hint
from tests.support.witness_tables import witnesses


def test_all_three_input_tables() -> None:
    for n in range(1, 4):
        for table in witnesses(n):
            template = cyclic_tag(table)
            # At most 2 * 2**m + 2n + 2 plus a 0 per 0 row.
            # Named minority markers shrink this; constants use n + 2. An ignored
            # input's rule is empty.
            essential = essential_inputs(table, n)
            m = len(essential)
            zeros = read_at(table, essential, n).count("0")
            size = n + 2 if len(set(table)) == 1 else 2 * 2**m + 2 * n + 2 + zeros
            assert len(template) <= size, table
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
    from esolangs.languages.cyclic_tag.tests.oracle_checks import check_raw_cyclic_tag

    check_raw_cyclic_tag()
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


def test_native_completion_reports_the_dump_and_run_keeps_its_return_contract(
    monkeypatch,
):
    io = ScriptedIO()
    report = _execute(",1", io)
    assert report.kind is Completion.POST_HALT
    assert report.cycle is None
    assert io.getvalue() == "1"
    assert run(",1", ScriptedIO()) is None
    from esolangs.languages.cyclic_tag import interpreter
    from tests.support.prepared_support import check_image_reuse

    check_image_reuse(
        "Cyclic tag",
        "0 ; , 1",
        interpreter,
        "_parse",
        monkeypatch,
        cases=(("", "0"),) * 3,
    )
