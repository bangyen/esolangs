"""Worker proof records preserve live IO and refuse unsupported verdicts."""

import copy
import json

import pytest

import esolangs
from esolangs import compat
from esolangs.registry import LANGUAGES
from esolangs.runtime._isolated import _decode, termination_result_isolated
from esolangs.runtime._lifecycle import BoundaryCycle
from esolangs.runtime._proof import BranchProof, CycleDecision
from esolangs.runtime._result_wire import decode_decision, encode_decision
from esolangs.runtime._termination import _termination_result
from esolangs.vm import make_vm
from tests.support.reference import REFERENCE


def _request(name, bit):
    lang = LANGUAGES[name]
    template = compat.generate(name, "01")
    source = (
        compat.instantiate(name, template, [bit]) if lang.parameterized else template
    )
    stdin = "" if lang.parameterized else esolangs.encode_inputs(name, [bit])
    return source, stdin


@pytest.mark.medium
def test_actual_termination_workers_retain_every_halt_and_cycle():
    for name, lang in LANGUAGES.items():
        if lang.contract.answer_mode != "termination":
            continue
        for bit in (0, 1):
            source, stdin = _request(name, bit)
            native = _termination_result(name, source, stdin, None)
            worker = termination_result_isolated(name, source, stdin, 5)
            assert worker == native
            assert worker.observation.completion is None
            assert worker.decision.halts is (bit == 0)
            if worker.decision.cycle is not None:
                cycle = worker.decision.cycle
                replay = make_vm(name, source, stdin=stdin)
                for _ in range(cycle.first_pass):
                    replay.step()
                assert replay.snapshot() == cycle.state
                for _ in range(cycle.repeat_pass - cycle.first_pass):
                    replay.step()
                assert replay.snapshot() == cycle.state


@pytest.mark.medium
def test_actual_branch_workers_retain_the_complete_graph():
    reached = 0
    for name, lang in LANGUAGES.items():
        if not lang.runtime.random:
            continue
        source, stdin = _request(name, 1)
        try:
            native = _termination_result(name, source, stdin, None)
        except (TimeoutError, TypeError):
            continue  # Unforkable input or draw-dependent halting remains undecided.
        if native.decision.branches is None:
            continue
        worker = termination_result_isolated(name, source, stdin, 5)
        assert worker == native
        assert worker.decision.branches.states_examined > 0
        model = make_vm(name, source, stdin=stdin)._machine
        for state, outcomes in worker.decision.branches.transitions:
            assert tuple(model.branching_successors(state, 10_000)) == outcomes
            assert not model.branching_halted(state)
        if worker.decision.halts:
            assert model.branching_halted(worker.decision.branches.terminal)
        reached += 1
    assert reached > 0


@pytest.mark.medium
def test_proof_deadlines_keep_output_without_claiming_divergence():
    source = "+.[>+]"
    with pytest.raises(esolangs.ExecutionTimeoutError) as native:
        _termination_result(REFERENCE, source, "", 0.01)
    assert native.value.partial_output == "\x01"
    with pytest.raises(esolangs.ExecutionTimeoutError) as worker:
        termination_result_isolated(REFERENCE, source, "", 1, max_output=1)
    assert worker.value.partial_output == "\x01"


def test_wire_decisions_require_proof_and_matching_counts():
    records = [
        CycleDecision(halts=False, commands=1, cycle=BoundaryCycle((0,), 0, 1, 1)),
        CycleDecision(
            halts=False,
            commands=None,
            branches=BranchProof(0, ((0, (0,)),), halts=False),
        ),
    ]
    for record in records:
        wire = json.loads(json.dumps(encode_decision(record)))
        assert decode_decision(wire) == record
        broken = copy.deepcopy(wire)
        broken["cycle"] = broken["branches"] = None
        with pytest.raises(ValueError, match=r"evidence|count"):
            decode_decision(broken)
    broken = json.loads(json.dumps(encode_decision(records[0])))
    broken["commands"] = 2
    with pytest.raises(ValueError, match="evidence"):
        decode_decision(broken)


def test_a_plain_worker_result_cannot_become_a_verdict():
    with pytest.raises(
        esolangs.InterpreterLimitError, match="invalid isolated"
    ) as caught:
        _decode('{"output":"prefix"}\n{"result":"0"}\n', expired=False)
    assert caught.value.partial_output == "prefix"
