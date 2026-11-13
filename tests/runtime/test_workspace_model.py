"""Semantic workspace components survive storage and cycle-snapshot regrouping."""

import csv
from pathlib import Path

import pytest

import esolangs
from esolangs.languages.brainfuck.interpreter import _WORKSPACE_MODEL, _Machine
from esolangs.registry import LANGUAGES
from esolangs.runtime._lifecycle import Completion
from esolangs.runtime._state import WorkspaceModel, WorkspaceSnapshot, WorkspaceVariant
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_workspace, complete_vm, make_vm
from scripts.benchmark import WrittenState, state_bits
from tests.interpreters.semantic_oracles import brainfuck
from tests.support.workspace_oracle import WorkspaceOracle, WorkspaceWitness


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

    variants = [
        WorkspaceVariant(kind, ("i",)) for kind in ("command", "print", "query")
    ]
    assert len(set(variants)) == 3
    assert [state_bits(value, {}) for value in variants] == [8, 8, 8]
    model = WorkspaceModel("typed-v1", ("value",))
    meter = WrittenState(model.capture(value=variants[0]))
    meter.sample(model.capture(value=variants[1]))
    assert meter.bits == 8
    with pytest.raises(ValueError, match="identifier"):
        WorkspaceVariant("bad kind", ())
    with pytest.raises(TypeError, match="tuple"):
        WorkspaceVariant("valid", [])
    with pytest.raises(TypeError, match="unhashable"):
        WorkspaceVariant("valid", ([],))

    import os
    import pickle
    import subprocess
    import sys

    value = WorkspaceVariant("Print", ("i",))
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import pickle, sys; "
            "from esolangs.runtime._state import WorkspaceVariant; "
            "value = pickle.loads(sys.stdin.buffer.read()); "
            "expected = WorkspaceVariant('Print', ('i',)); "
            "assert value == expected and hash(value) == hash(expected)",
        ],
        input=pickle.dumps(value),
        env={**os.environ, "PYTHONHASHSEED": "73"},
        check=True,
    )


def test_accounting_refuses_a_mid_run_model_change():
    model = WorkspaceModel("two-v1", ("cursor", "cells"))
    written = WrittenState(model.capture(cursor=0, cells=(0,)))
    for changed in (
        WorkspaceModel("two-v2", model.components).capture(cursor=1, cells=(1,)),
        WorkspaceModel("two-v1", ("cells", "cursor")).capture(cursor=1, cells=(1,)),
    ):
        with pytest.raises(ValueError, match="model changed"):
            written.sample(changed)
    oracle = WorkspaceOracle(model.capture(cursor=0, cells=(0,)))
    for value, bits in ((False, 1), (0, 1), (255, 8), (-255, 9)):
        assert oracle.width(value) == bits
    for cursor, cells, expected in ((1, (8, -1), 7), (2, (0,), 8)):
        snapshot = model.capture(cursor=cursor, cells=cells)
        written.sample(snapshot)
        oracle.sample(snapshot)
        assert written.bits == oracle.bits == expected
    # A missing component peak must be observable, rather than a vacuous match.
    written._peaks[1] = 0
    with pytest.raises(AssertionError):
        assert written.bits == oracle.bits
    with pytest.raises(TypeError, match="undeclared workspace payload"):
        oracle.width([])
    witness = WorkspaceWitness(model)
    saved = model.capture(cursor=0, cells=(0,))
    witness.sample(saved, saved.parts)
    for cursor in (1, 2):
        captured = model.capture(cursor=cursor, cells=(0,))
        witness.sample(captured, captured.parts)
    witness.finish()
    # Corrupt an older capture after its neighbor has already been checked.
    object.__setattr__(saved, "parts", (7, (0,)))
    assert witness.previous[0] == witness.previous[1]
    with pytest.raises(AssertionError):
        witness.finish()


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
    grouped = WorkspaceModel("brainfuck-grouped-test-v1", ("state", "input_cursor"))
    regrouped = WrittenState(WorkspaceSnapshot(grouped, vm.snapshot()))
    while not vm.halted:
        vm.step()
        semantic.sample(_capture_workspace(vm))
        regrouped.sample(WorkspaceSnapshot(grouped, vm.snapshot()))
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
    from tests.support.samples import SAMPLES

    def forbidden(*_args):
        raise AssertionError("cycle snapshot reached accounting")

    non_boolean = 0
    for language in LANGUAGES.values():
        if language.backend is not None:
            continue
        source, stdin = SAMPLES[language.name]
        artifact = esolangs.ProgramArtifact(source, language.name)
        vm = make_vm(language.name, artifact, stdin=stdin)
        saved = _capture_workspace(vm)
        retained = {saved}
        measured = WrittenState(saved)
        oracle = WorkspaceOracle(saved)
        monkeypatch.setattr(vm._machine, "snapshot", forbidden)
        for _ in range(len(source) + 1):
            if vm.halted:
                break
            vm.step()
            snapshot = _capture_workspace(vm)
            measured.sample(snapshot)
            oracle.sample(snapshot)
            assert measured.bits == oracle.bits
            assert saved in retained
        assert vm.halted
        assert measured.bits > 0
        assert isinstance(_capture_workspace(vm), WorkspaceSnapshot)
        assert saved in retained
        assert vm.output == esolangs.run(language.name, artifact, stdin=stdin).output
        non_boolean += 1
    assert non_boolean > 0
    vm = make_vm("Brainfuck", "+.")
    monkeypatch.setattr(_Machine, "snapshot", forbidden)
    with monkeypatch.context() as patch:
        patch.setattr(_Machine, "workspace_snapshot", lambda _self: ())
        with pytest.raises(TypeError, match="WorkspaceSnapshot"):
            _capture_workspace(vm)
    with monkeypatch.context() as patch:
        patch.delattr(_Machine, "workspace_snapshot")
        with pytest.raises(TypeError, match="requires workspace_snapshot"):
            _capture_workspace(vm)
    with monkeypatch.context() as patch:
        patch.setattr(_Machine, "workspace_snapshot", None)
        with pytest.raises(TypeError, match="requires workspace_snapshot"):
            _capture_workspace(vm)

    class SnapshotOnly:
        snapshot = forbidden

    with pytest.raises(TypeError, match="registered VM"):
        _capture_workspace(SnapshotOnly())


def _declared_boolean_models():
    ledger = Path(__file__).with_name("workspace_models.csv")
    with ledger.open() as source:
        rows = list(csv.DictReader(source))
    listed = {row["language"] for row in rows}
    assert listed == LANGUAGES.keys(), (
        f"{ledger.name}: add rows for {sorted(LANGUAGES.keys() - listed)}, "
        f"drop {sorted(listed - LANGUAGES.keys())}"
    )
    assert len(rows) == len(LANGUAGES)
    for row in rows:
        assert row["workspace"] in {"owned-adapter", "inherited-adapter"}, row
        assert row["workspace_model"] not in {"", "needs-review"}, row
    return [
        (row["language"], row["workspace_model"])
        for row in rows
        if row["boolean_backend"] == "yes"
    ]


# The complete word-store accounting witness takes 2.04 s in a serial run.
@pytest.mark.medium
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
    oracle = WorkspaceOracle(saved)
    monkeypatch.setattr(type(vm._machine), "snapshot", lambda _self: ())
    capabilities = LANGUAGES[name].runtime.capabilities
    periodic = (
        capabilities is not None and capabilities.completion is Completion.PERIODIC
    )
    from tests.proofs.execution import FORMULAS

    budget = 5000
    if name in FORMULAS:
        bound, _, arities = FORMULAS[name]
        if 1 in arities:
            budget = max(budget, bound(1, artifact.source) + 1)
    boundaries = set()
    for _ in range(budget):
        if periodic and vm.ip == 0:
            state = _capture_workspace(vm)
            if state in boundaries:
                break
            boundaries.add(state)
        if vm.halted:
            break
        vm.step()
        captured = _capture_workspace(vm)
        measured.sample(captured)
        oracle.sample(captured)
        assert measured.bits == oracle.bits, (name, captured)
        assert saved in retained
    else:
        pytest.fail(f"one-input accounting witness exceeded {budget} commands")
    if periodic:
        assert _capture_workspace(vm) in boundaries
        vm._machine.interrupt()
        vm.step()
    else:
        complete_vm(vm)
    measured.sample(_capture_workspace(vm))
    oracle.sample(_capture_workspace(vm))
    assert measured.bits == oracle.bits, name
    assert measured.bits > 0
    if termination:
        assert vm.halted
    else:
        assert esolangs.read_answer(name, vm.output) == expected
