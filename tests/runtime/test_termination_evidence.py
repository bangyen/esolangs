"""Decision records retain replayable cycles and complete branching closures."""

import pytest

from esolangs._cycles import _halt_or_cycle_result
from esolangs.debugger import make_debugger
from esolangs.runtime._lifecycle import BoundaryCycle
from esolangs.runtime._proof import BranchProof, CycleDecision, checked_decision
from esolangs.vm import make_vm, run_until_halt_or_all_branches_cycle
from tests.support.reference import REFERENCE


@pytest.mark.parametrize("factory", [make_vm, make_debugger])
def test_actual_cycle_boundaries_replay_with_the_same_input_cursor(factory):
    machine = factory(REFERENCE, ",.[]", stdin="A")
    result = checked_decision(_halt_or_cycle_result(machine, 20))
    assert result.halts is False
    assert result.cycle.commands_per_pass == 1
    assert result.commands == result.cycle.repeat_pass
    assert machine.output == "A"

    replay = factory(REFERENCE, ",.[]", stdin="A")
    for _ in range(result.cycle.first_pass):
        replay.step()
    assert replay.snapshot() == result.cycle.state
    for _ in range(result.cycle.repeat_pass - result.cycle.first_pass):
        replay.step()
    assert replay.snapshot() == result.cycle.state
    assert not replay.halted


@pytest.mark.parametrize(("source", "commands"), [("", 0), (",.", 2)])
def test_halt_counts_include_the_exact_budget_boundary(source, commands):
    result = checked_decision(
        _halt_or_cycle_result(make_vm(REFERENCE, source, stdin="A"), commands)
    )
    assert result == CycleDecision(halts=True, commands=commands)


def test_a_growing_state_exhausts_its_budget_without_a_verdict():
    with pytest.raises(TimeoutError, match="neither halted nor repeated"):
        _halt_or_cycle_result(make_vm(REFERENCE, "+[>+]"), 20)


class _Branches:
    halted = False

    def __init__(self, *, halting=False):
        self.halting = halting

    def snapshot(self):
        return 0

    def step(self):
        pytest.fail("branch exploration must not consume a live draw")

    def branching_snapshot(self):
        return 0

    def branching_halted(self, state):
        return self.halting and state == 2

    def branching_successors(self, state, _limit):
        return {0: (1, 2), 1: (1,), 2: (0,)}[state]


def test_branching_divergence_keeps_every_explored_outcome():
    machine = _Branches()
    result = checked_decision(_halt_or_cycle_result(machine))
    assert result.halts is False
    assert result.commands is None
    assert result.cycle is None
    assert result.branches.forked is True
    assert result.branches.root == 0
    assert result.branches.states_examined == 3
    graph = dict(result.branches.transitions)
    assert set(graph) == {0, 1, 2}
    for state, outcomes in graph.items():
        assert outcomes == machine.branching_successors(state, 10)
        assert set(outcomes) <= graph.keys()
        assert not machine.branching_halted(state)


def test_a_possible_branching_halt_is_not_this_runs_verdict():
    machine = _Branches(halting=True)
    assert run_until_halt_or_all_branches_cycle(machine) is True
    with pytest.raises(TypeError, match="depends on its own draws"):
        _halt_or_cycle_result(machine)


def test_an_open_branch_graph_cannot_claim_divergence():
    with pytest.raises(ValueError, match="closed graph"):
        BranchProof(0, ((0, (1,)),), halts=False)
    for transitions, halts, terminal in (
        (((9, (10,)),), True, 10),
        (((0, (0,)), (9, (10,))), True, 10),
        (((0, (0,)), (9, (9,))), False, None),
        (((0, (1,)), (1, (1,))), True, 1),
        ([(0, (0,))], False, None),
        (([0, (0,)],), False, None),
        (((0, [0]),), False, None),
    ):
        with pytest.raises(ValueError, match=r"unreachable|outgoing|containers"):
            BranchProof(0, transitions, halts=halts, terminal=terminal)
    # DFS may stop with an unexplored sibling when it reaches the terminal.
    partial = BranchProof(0, ((0, (1, 2)), (2, (3,))), halts=True, terminal=3)
    assert partial.states_examined == 3
    with pytest.raises(ValueError, match="draws"):
        checked_decision(CycleDecision(halts=True, commands=None, branches=partial))
    assert BranchProof(None, (), halts=True).states_examined == 1


@pytest.mark.parametrize(
    "result",
    [
        CycleDecision(halts=False, commands=0),
        CycleDecision(halts=False, commands=1, cycle=BoundaryCycle(0, 0, 2, 1)),
    ],
)
def test_a_nominal_record_without_valid_evidence_is_refused(result):
    with pytest.raises(ValueError, match=r"evidence|cycle|count"):
        checked_decision(result)
