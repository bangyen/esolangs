"""Semantic workspace components survive storage and cycle-snapshot regrouping."""

import csv
from pathlib import Path

import pytest

import esolangs
from esolangs.languages.brainfuck.interpreter import _WORKSPACE_MODEL, _Machine
from esolangs.registry import LANGUAGES
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_workspace, complete_vm, make_vm
from scripts.benchmark import WrittenState
from tests.interpreters.semantic_oracles import brainfuck


def test_model_components_are_named_complete_and_immutable():
    assert _WORKSPACE_MODEL.name == "brainfuck-v1"
    assert _WORKSPACE_MODEL.components == (
        "instruction",
        "pointer",
        "tape",
        "input_cursor",
    )
    model = WorkspaceModel("two-v1", ("cursor", "cells"))
    snapshot = model.capture(cells=(1, 2), cursor=3)
    assert snapshot.parts == (3, (1, 2))
    assert hash(snapshot) == hash(model.capture(cursor=3, cells=(1, 2)))
    for values in ({"cursor": 3}, {"cursor": 3, "cells": (), "cache": 0}):
        with pytest.raises(ValueError, match="declared components"):
            model.capture(**values)
    with pytest.raises(TypeError, match="unhashable"):
        model.capture(cursor=0, cells=[])
    with pytest.raises(ValueError, match="match its model"):
        WorkspaceSnapshot(model, (0,))
    for components in ((), ("cursor", "cursor"), ("bad name",)):
        with pytest.raises(ValueError, match="distinct components"):
            WorkspaceModel("bad-v1", components)


def test_accounting_refuses_a_mid_run_model_change():
    model = WorkspaceModel("two-v1", ("cursor", "cells"))
    written = WrittenState(model.capture(cursor=0, cells=(0,)))
    for changed in (
        WorkspaceModel("two-v2", model.components).capture(cursor=1, cells=(1,)),
        WorkspaceModel("two-v1", ("cells", "cursor")).capture(cursor=1, cells=(1,)),
        (1, (1,)),
    ):
        with pytest.raises(ValueError, match="model changed"):
            written.sample(changed)


class _PaddedMachine(_Machine):
    """A reordered store with spare tape capacity and a nonsemantic cache."""

    @property
    def state(self):
        return (
            self._packed["pc"],
            self._packed["head"],
            tuple(self._packed["buffer"][: self._packed["used"]]),
        )

    @state.setter
    def state(self, state):
        pc, head, tape = state
        self._packed = {
            "buffer": bytearray(tape) + bytearray(16),
            "used": len(tape),
            "head": head,
            "pc": pc,
            "cache": "excluded backing storage",
        }


@pytest.mark.parametrize(
    ("code", "stdin"),
    [
        ("", ""),
        ("<+<++>>.<.<.", ""),
        ("++[>--<-]>.", ""),
        (",.>,.<,.", "λāé"),
        ("-[+].", ""),
        ("+[]", ""),
    ],
)
def test_padded_storage_keeps_semantic_traces_and_exact_workspace(code, stdin):
    machines = [
        _Machine(code, ScriptedIO(stdin)),
        _PaddedMachine(code, ScriptedIO(stdin)),
    ]
    written = [WrittenState(machine.workspace_snapshot()) for machine in machines]
    for steps in range(96):
        states = [machine.workspace_snapshot() for machine in machines]
        assert states[0] == states[1]
        for machine, accounting in zip(machines, states, strict=True):
            assert accounting.model is _WORKSPACE_MODEL
            assert accounting.parts == machine.snapshot()
            expected = brainfuck(code, stdin, steps)
            assert (
                machine.io.getvalue(),
                machine.tape,
                machine.ind,
                machine.io.progress(),
                machine.halted,
            ) == (
                expected.output,
                expected.memory,
                expected.ip,
                expected.consumed,
                expected.halted,
            )
        if machines[0].halted:
            break
        for machine, measured in zip(machines, written, strict=True):
            machine.step()
            measured.sample(machine.workspace_snapshot())
        assert written[0].bits == written[1].bits


def test_cycle_snapshot_regrouping_cannot_change_workspace(monkeypatch):
    monkeypatch.setattr(
        _Machine, "snapshot", lambda self: (self.state, self.io.progress())
    )
    vm = make_vm("Brainfuck", "+.")
    semantic = WrittenState(_capture_workspace(vm))
    regrouped = WrittenState(vm.snapshot())
    while not vm.halted:
        vm.step()
        semantic.sample(_capture_workspace(vm))
        regrouped.sample(vm.snapshot())
    # PC: two bits; written tape: one. The regrouped tuple also counts the idle pointer.
    assert semantic.bits == 3
    assert regrouped.bits == 4
    assert vm.output == "\x01"


def test_input_progress_and_failed_reads_are_observed():
    vm = make_vm("Brainfuck", ",>,", stdin="A")
    vm.step()
    observed = _capture_workspace(vm)
    assert observed.parts == (1, 0, (65,), 1)
    vm.step()
    before = _capture_workspace(vm)
    with pytest.raises(EOFError):
        vm.step()
    assert _capture_workspace(vm) == before
    with pytest.raises(ValueError, match="declared components"):
        _WORKSPACE_MODEL.capture(instruction=1, pointer=0, tape=(65,))


def test_an_invalid_owned_adapter_cannot_fall_back(monkeypatch):
    monkeypatch.setattr(_Machine, "workspace_snapshot", lambda self: self.snapshot())
    with pytest.raises(TypeError, match="WorkspaceSnapshot"):
        _capture_workspace(make_vm("Brainfuck", "+."))


def _declared_boolean_models():
    ledger = Path(__file__).resolve().parents[2] / "docs/migration-status.csv"
    with ledger.open() as source:
        return [
            (row["language"], row["workspace_model"])
            for row in csv.DictReader(source)
            if row["workspace"] != "snapshot-fallback"
            and row["boolean_backend"] == "yes"
        ]


@pytest.mark.parametrize(("name", "model"), _declared_boolean_models())
def test_declared_models_keep_immutable_accounting_without_cycle_keys(
    name, model, monkeypatch
):
    contract = LANGUAGES[name].contract
    termination = contract.answer_mode == "termination"
    expected = str(contract.answer_values.index("halts")) if termination else "0"
    table = str(1 - int(expected)) + expected
    artifact = esolangs.generate(name, table)
    if isinstance(artifact, esolangs.TemplateArtifact):
        artifact = esolangs.instantiate(name, artifact, [1])
        stdin = ""
    else:
        stdin = str(esolangs.encode_inputs(name, [1], truth_table=table))
    vm = make_vm(name, artifact, stdin=stdin)
    saved = _capture_workspace(vm)
    assert isinstance(saved, WorkspaceSnapshot)
    assert saved.model.name == model
    retained = {saved}
    measured = WrittenState(saved)
    monkeypatch.setattr(type(vm._machine), "snapshot", lambda _self: ())
    capabilities = LANGUAGES[name].runtime.capabilities
    periodic = (
        capabilities is not None and capabilities.completion is Completion.PERIODIC
    )
    boundaries = set()
    for _ in range(5000):
        if periodic and vm.ip == 0:
            state = _capture_workspace(vm)
            if state in boundaries:
                break
            boundaries.add(state)
        if vm.halted:
            break
        vm.step()
        measured.sample(_capture_workspace(vm))
        assert saved in retained
    else:
        pytest.fail("one-input accounting witness did not complete")
    if periodic:
        assert _capture_workspace(vm) in boundaries
        vm._machine.interrupt()
        vm.step()
    else:
        complete_vm(vm)
    measured.sample(_capture_workspace(vm))
    assert measured.bits > 0
    if termination:
        assert vm.halted
    else:
        assert esolangs.read_answer(name, vm.output) == expected
