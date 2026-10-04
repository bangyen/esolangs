"""Flowchart first-visit junction ties preserve memory and node rules."""

from itertools import product

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs.interpreters.grid_based.flowchart import _Machine
from esolangs.interpreters.io import ScriptedIO
from esolangs.tagged import _Tagged
from esolangs.tools.flowchart import flowchart
from esolangs.vm import complete_vm, make_vm
from tests.cli_support import call_both

WITNESS = "\n".join(
    [
        "          (( ))              ( )",
        "            │                 │",
        "           \\ \\               [ }",
        "            │                 │",
        "            ├─────────────────┘",
        "            │",
        "           [ ]",
        "            │",
        "           \\ \\",
        "            │",
        "          (( ))",
    ]
)


@pytest.mark.parametrize(
    ("policy", "expected"), [("right_first", "1"), ("left_first", "0")]
)
def test_first_visit_witness_vm_and_portable(policy, expected):
    settings = DialectSettings(junction_tie_break=policy)
    assert esolangs.run("Flowchart", WITNESS, settings=settings) == expected
    vm = make_vm("Flowchart", WITNESS, settings=settings)
    assert complete_vm(vm, 100) == expected
    saved = esolangs.load_program(
        "Flowchart",
        esolangs.dump_program("Flowchart", _Tagged(WITNESS, "Flowchart", settings)),
    )
    assert esolangs.run("Flowchart", saved) == expected
    assert (
        esolangs.run(
            "Flowchart",
            saved,
            settings=DialectSettings(junction_tie_break="right_first"),
        )
        == "1"
    )


@pytest.mark.parametrize("policy", ["right_first", "left_first"])
def test_remembered_exit_wins(policy):
    machine = _Machine(WITNESS.splitlines(), ScriptedIO(), junction_tie_break=policy)
    for _ in range(100):
        pointer = machine.pointers[0]
        if (pointer.row, pointer.col) == (4, 12):
            break
        machine.step()
    else:
        pytest.fail("junction was not reached")
    machine.pointers[0] = pointer.remembering((4, 12), (1, 0))
    machine.step()
    assert machine.pointers[0].d == (1, 0)


def test_invalid_settings_and_metadata():
    with pytest.raises(ValueError, match="junction_tie_break"):
        flowchart("01", junction_tie_break="bad")
    with pytest.raises(esolangs.ArgumentError, match="junction_tie_break"):
        esolangs.run(
            "Flowchart", WITNESS, settings=DialectSettings(junction_tie_break="bad")
        )
    option = esolangs.describe("Flowchart")["dialect_settings"]["junction_tie_break"]
    assert option["default"] == "right_first"
    assert option["choices"] == ("right_first", "left_first")


@pytest.mark.medium
@pytest.mark.parametrize("policy", ["right_first", "left_first"])
@pytest.mark.parametrize(
    ("schedule", "cursor"), product(["creation", "reverse"], ["pointer", "shared"])
)
@pytest.mark.parametrize("chunk", range(16))
def test_generated_corpus(policy, schedule, cursor, chunk):
    settings = DialectSettings(
        junction_tie_break=policy, scheduling=schedule, deque_cursor=cursor
    )
    for inputs in range(1, 4):
        for value in range(chunk, 1 << (1 << inputs), 16):
            table = format(value, f"0{1 << inputs}b")
            for layout in [{}, {"balance": True}, {"width": 20}]:
                source = esolangs.generate(
                    "Flowchart", table, settings=settings, **layout
                )
                assert esolangs.evaluate("Flowchart", source, inputs=inputs) == table


@pytest.mark.parametrize("policy", ["right_first", "left_first"])
def test_cli_portable_and_isolation(policy, tmp_path, capsys):
    settings = DialectSettings(junction_tie_break=policy)
    path = tmp_path / "flowchart-junction.json"
    path.write_text(
        esolangs.dump_program("Flowchart", _Tagged(WITNESS, "Flowchart", settings))
    )
    output, error = call_both(["run", "--portable", "Flowchart", str(path)], capsys)
    assert output.strip() == ("1" if policy == "right_first" else "0")
    assert error == ""
    source = esolangs.generate("Flowchart", "0110", settings=settings, balance=True)
    assert esolangs.evaluate("Flowchart", source, inputs=2, isolated=True) == "0110"


@pytest.mark.parametrize("policy", ["right_first", "left_first"])
def test_straight_exit_wins(policy):
    rows = WITNESS.splitlines()
    rows[4] = "(( ))───────┼─────────────────┘"
    machine = _Machine(rows, ScriptedIO(), junction_tie_break=policy)
    for _ in range(100):
        pointer = machine.pointers[0]
        if (pointer.row, pointer.col) == (4, 12):
            break
        machine.step()
    else:
        pytest.fail("junction was not reached")
    machine.step()
    assert machine.pointers[0].d == (0, -1)


@pytest.mark.parametrize("policy", ["right_first", "left_first"])
def test_switches_redecide_in_wiki_cat(policy):
    from tests.interpreters.test_flowchart import CAT

    source = "\n".join(CAT)
    assert (
        esolangs.run(
            "Flowchart",
            source,
            stdin="0101",
            settings=DialectSettings(junction_tie_break=policy),
        )
        == "01010"
    )
