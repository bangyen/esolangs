"""Bit-tape accounting excludes backing capacity and cycle-snapshot grouping."""

from types import SimpleNamespace

from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.bit_tape import _BitTapeMachine
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState


def test_bit_workspace_preserves_exact_peaks_across_storage_and_cycle_views():
    class Machine(_BitTapeMachine):
        _workspace_model = WorkspaceModel(
            "bit-tape-test-v1", ("control", "ones", "input_cursor")
        )

    machine = Machine(",;,;,;" + "," * 9, ScriptedIO("é"))

    def parts():
        return (tuple(machine.state), frozenset(machine.ones), machine.io.progress())

    reference = WorkspaceModel(
        "bit-reference-test-v1", ("control", "ones", "input_cursor")
    )
    legacy = WrittenState(WorkspaceSnapshot(reference, parts()))
    measured = WrittenState(machine.workspace_snapshot())
    machine.snapshot = lambda: ()
    for _ in range(len(machine.code) + 1):
        state = machine.state
        snapshot = machine.workspace_snapshot()
        assert snapshot.parts == parts()
        machine.state = SimpleNamespace(**state._asdict(), capacity=[0] * 128)
        assert machine.workspace_snapshot() == snapshot
        machine.state = state
        measured.sample(snapshot)
        legacy.sample(WorkspaceSnapshot(reference, parts()))
        assert measured.bits == legacy.bits
        if machine.halted:
            break
        machine.step()
    assert (snapshot.parts[-1], machine.io.past_end) == (1, 1)
    assert snapshot.parts[0][2:4] == (0, 4)
