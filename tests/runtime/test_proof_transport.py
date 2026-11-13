"""Worker proof records preserve live IO and refuse unsupported verdicts."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

import esolangs
from esolangs.debugger import make_debugger
from esolangs.registry import LANGUAGES
from esolangs.results import ExecutionResult
from esolangs.runtime._isolated import termination_result_isolated
from esolangs.runtime._lifecycle import BoundaryCycle
from esolangs.runtime._proof import BranchProof, CycleDecision
from esolangs.runtime._result_wire import (
    decode_decision,
    encode_decision,
    encode_result,
)
from esolangs.vm import _capture_observation, make_vm
from tests.support.certification_barrier import guarded_worker
from tests.support.execution import run_observed, termination_observed
from tests.support.reference import REFERENCE
from tests.support.worker_response import _decode


def _request(name, bit):
    lang = LANGUAGES[name]
    template = esolangs.generate(name, "01")
    source = (
        esolangs.instantiate(name, template, [bit]) if lang.parameterized else template
    )
    stdin = "" if lang.parameterized else esolangs.encode_inputs(name, [bit])
    return source, stdin


def _replay_termination(name, source, stdin, result):
    decision = result.decision
    assert decision.branches is None
    assert decision.commands is not None
    debugger = make_debugger(name, source, stdin=stdin)
    retained = None
    for step in range(decision.commands + 1):
        if decision.cycle is not None and step == decision.cycle.first_pass:
            retained = debugger.snapshot()
        if step == decision.commands:
            break
        assert not debugger.halted
        debugger.step()
    assert debugger.halted is decision.halts
    assert debugger.observation.steps == decision.commands
    assert _capture_observation(debugger.vm) == result.observation
    assert result.observation.completion is None
    if decision.cycle is not None:
        assert decision.cycle.commands_per_pass == 1
        assert decision.cycle.repeat_pass == decision.commands
        assert debugger.snapshot() == retained == decision.cycle.state
        assert debugger.observation.completion is None
    else:
        # A halting proof has not requested a post-halt output dump.
        assert (
            debugger.observation.completion is None
        ) is debugger.dumps_on_the_post_halt_step
        native = run_observed(name, source, stdin=stdin, timeout=5)
        debugger.step()
        completed = debugger.observation
        assert completed == replace(native, steps=decision.commands)
        debugger.step()
        assert debugger.observation == completed


@pytest.mark.medium
def test_actual_termination_workers_retain_every_halt_and_cycle():
    cases = []
    refused = 0
    coverage = {}
    tables = [f"{mask:0{1 << n}b}" for n in (1, 2) for mask in range(1 << (1 << n))]
    for name, lang in LANGUAGES.items():
        if lang.contract.answer_mode != "termination":
            continue
        coverage[name] = [0, 0]
        for table in tables:
            try:
                artifact = esolangs.generate(name, table)
            except esolangs.GeneratorCapError:
                refused += len(table)
                coverage[name][1] += len(table)
                continue
            inputs = len(table).bit_length() - 1
            for row, answer in enumerate(table):
                bits = [int(bit) for bit in f"{row:0{inputs}b}"]
                source = (
                    esolangs.instantiate(name, artifact, bits)
                    if lang.parameterized
                    else artifact
                )
                stdin = (
                    ""
                    if lang.parameterized
                    else esolangs.encode_inputs(name, bits, truth_table=table)
                )
                native = termination_observed(name, source, stdin, 5)
                assert native.decision.halts is (
                    lang.contract.answer_values[int(answer)] == "halts"
                )
                _replay_termination(name, source, stdin, native)
                cases.append((name, source, stdin, native))
                coverage[name][0] += 1
    assert len(coverage) == 3
    assert all(
        admitted > 0 and admitted + capped == 72
        for admitted, capped in coverage.values()
    )
    assert len(cases) == 180
    assert refused == 36
    assert sum(case[3].decision.halts for case in cases) == 91

    name, source, stdin, result = next(case for case in cases if case[3].decision.cycle)
    cycle = result.decision.cycle
    for damaged in (
        result._replace(
            decision=result.decision._replace(cycle=replace(cycle, state=("wrong",)))
        ),
        result._replace(
            observation=replace(
                result.observation, input_reads=result.observation.input_reads + 1
            )
        ),
        result._replace(
            decision=result.decision._replace(commands=result.decision.commands + 1)
        ),
    ):
        with pytest.raises(AssertionError):
            _replay_termination(name, source, stdin, damaged)

    def check_worker(case):
        name, source, stdin, native = case
        worker = termination_result_isolated(name, source, stdin, 5)
        assert worker == native, (name, source, stdin)
        return worker

    with guarded_worker(expected=len(cases)), ThreadPoolExecutor(max_workers=4) as pool:
        assert len(list(pool.map(check_worker, cases))) == len(cases)

    template = esolangs.TemplateArtifact(
        "$", REFERENCE, esolangs.TemplateBindings(setters=((">", "<"),))
    )
    with pytest.raises(esolangs.TemplateError, match="fill the template"):
        termination_result_isolated(REFERENCE, template, "", 5)


@pytest.mark.medium
def test_actual_branch_workers_retain_the_complete_graph():
    reached = refused = 0
    for name, lang in LANGUAGES.items():
        if not lang.runtime.random:
            continue
        source, stdin = _request(name, 1)
        try:
            native = termination_observed(name, source, stdin, 5)
        except esolangs.ExecutionCapError as error:
            if "cannot be safely forked" not in str(error):
                raise
            refused += 1
            continue
        assert native.decision.branches is not None
        with guarded_worker():
            worker = termination_result_isolated(
                name, source.source, stdin, 5, settings=source.settings
            )
        assert worker == native
        assert worker.decision.branches.states_examined > 0
        model = make_vm(name, source, stdin=stdin)._machine
        assert worker.decision.branches.root == model.branching_snapshot()
        for state, outcomes in worker.decision.branches.transitions:
            assert tuple(model.branching_successors(state, 10_000)) == outcomes
            assert not model.branching_halted(state)
        if worker.decision.halts:
            assert model.branching_halted(worker.decision.branches.terminal)
        reached += 1
    assert reached == 2
    assert refused == 10


@pytest.mark.medium
def test_proof_deadlines_keep_output_without_claiming_divergence():
    source = ",.+[>+]"
    with pytest.raises(esolangs.ExecutionTimeoutError) as native:
        termination_observed(REFERENCE, source, "A", 0.01)
    assert native.value.partial_output == "A"
    assert native.value.observation == ExecutionResult("A", 1, 1, 0)
    with pytest.raises(esolangs.ExecutionTimeoutError) as worker:
        termination_result_isolated(REFERENCE, source, "A", 1, max_output=1)
    assert worker.value.partial_output == "A"
    assert worker.value.observation is None


def test_wire_decisions_require_proof_and_matching_counts():
    streamed = json.dumps({"output": "prefix"}) + "\n"
    observation = encode_result(ExecutionResult("prefix", 0, 0, 0))

    def refuses(proof, pattern):
        with pytest.raises(ValueError, match=pattern):
            decode_decision(proof)
        packet = {"result": "prefix", "execution": observation, "termination": proof}
        with pytest.raises(
            esolangs.InterpreterLimitError, match="invalid isolated"
        ) as caught:
            _decode(streamed + json.dumps(packet), expired=False)
        assert caught.value.partial_output == "prefix"

    records = [
        CycleDecision(halts=False, commands=1, cycle=BoundaryCycle((0,), 0, 1, 1)),
        *(
            CycleDecision(halts=proof.halts, commands=None, branches=proof)
            for proof in (
                BranchProof(0, ((0, (0,)),), halts=False),
                BranchProof(0, ((0, (1,)), (1, (2,))), halts=True, terminal=2),
            )
        ),
    ]
    for record in records:
        wire = json.loads(json.dumps(encode_decision(record)))
        assert decode_decision(wire) == record
        packet = {"result": "prefix", "execution": observation, "termination": wire}
        assert _decode(streamed + json.dumps(packet), expired=False).decision == record
        nested = "cycle" if record.cycle is not None else "branches"
        for part in (None, nested):
            target = wire if part is None else wire[part]
            for key in (*target, "obsolete"):
                malformed = copy.deepcopy(packet)
                changed = malformed["termination"]
                if part is not None:
                    changed = changed[part]
                if key == "obsolete":
                    changed[key] = True
                else:
                    del changed[key]
                refuses(
                    malformed["termination"],
                    r"invalid (termination|boundary|branching)",
                )
        broken = copy.deepcopy(wire)
        broken["cycle"] = broken["branches"] = None
        with pytest.raises(ValueError, match=r"evidence|count"):
            decode_decision(broken)
    broken = json.loads(json.dumps(encode_decision(records[0])))
    broken["commands"] = 2
    with pytest.raises(ValueError, match="evidence"):
        decode_decision(broken)
    for transitions, halts, terminal in (
        ([[0, []]], False, None),
        ([[0, [1]], [1, []]], False, None),
        ([[9, [10]]], True, 10),
        ([[0, [0]], [9, [10]]], True, 10),
        ([[0, [0]], [9, [9]]], False, None),
        ([[0, [1]], [1, [1]]], True, 1),
        ([[0, [1, 2]]], True, 2),
    ):
        broken = {
            "halts": halts,
            "commands": None,
            "cycle": None,
            "branches": {
                "root": 0,
                "transitions": transitions,
                "halts": halts,
                "terminal": terminal,
            },
        }
        refuses(broken, r"unreachable|outgoing|draws|closed")


def test_a_plain_worker_result_cannot_become_a_verdict():
    with pytest.raises(
        esolangs.InterpreterLimitError, match="invalid isolated"
    ) as caught:
        _decode('{"output":"prefix"}\n{"result":"0"}\n', expired=False)
    assert caught.value.partial_output == "prefix"
