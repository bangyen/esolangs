"""Detector guidance keeps undecided attempts separate from proofs."""

import pytest

import esolangs
from esolangs import vm


@pytest.mark.medium
@pytest.mark.parametrize(
    ("detector", "language", "source", "message", "hint"),
    [
        (
            "run_until_halt_or_cycle",
            "brainfuck",
            "+[]",
            "undecided after 0 steps: neither halted nor repeated a state",
            "supported growth detector",
        ),
        (
            "run_until_halt_or_all_branches_cycle",
            "Modulous",
            "[RND 2][END]",
            "undecided after 0 branching states: the reachable graph may be unbounded",
            "branching state limit",
        ),
        (
            "run_until_halt_or_ancestor",
            "Forbin",
            "main { return 0; }",
            (
                "undecided after 0 pushed frames: neither halted nor repeated "
                "an ancestor's entry state"
            ),
            "pushed-frame limit",
        ),
        (
            "run_until_halt_or_growth",
            "brainfuck",
            "+[]",
            (
                "undecided after 0 steps: neither halted nor grew "
                "by a provable translation"
            ),
            "run_until_halt_or_cycle",
        ),
        (
            "run_until_halt_or_value_growth",
            "Suffolk",
            "<",
            (
                "undecided after 0 steps: neither halted nor climbed "
                "by a provable affine step"
            ),
            "run_until_halt_or_cycle",
        ),
    ],
)
def test_detector_bounds_preserve_the_exact_diagnostic(
    detector, language, source, message, hint
):
    machine = vm.make_vm(language, source)
    with pytest.raises(TimeoutError) as caught:
        getattr(vm, detector)(machine, limit=0)
    assert type(caught.value) is TimeoutError
    assert str(caught.value) == message
    assert hint in caught.value.__notes__[0]


@pytest.mark.medium
@pytest.mark.parametrize(
    ("detector", "hint"),
    [
        ("run_until_halt_or_all_branches_cycle", "branching_successors"),
        ("run_until_halt_or_ancestor", "frame_entry_key"),
        ("run_until_halt_or_growth", "rightward-growing tape"),
        ("run_until_halt_or_value_growth", "unbounded affine values"),
    ],
)
def test_unsupported_detectors_name_the_needed_capability(detector, hint):
    with pytest.raises(TypeError) as caught:
        getattr(vm, detector)(vm.make_vm("Sophie", ""))
    assert type(caught.value) is TypeError
    assert str(caught.value).startswith("Sophie is not ")
    assert hint in caught.value.__notes__[0]


def test_cycle_detector_requires_a_snapshot_machine():
    with pytest.raises(TypeError) as caught:
        vm.run_until_halt_or_cycle(object())
    assert str(caught.value) == (
        "object is not steppable with a snapshot: neither it nor any machine "
        "it wraps provides the required members"
    )
    assert "step, halted and snapshot" in caught.value.__notes__[0]


@pytest.mark.medium
def test_fixed_input_does_not_make_branch_input_forkable():
    source = "[INP INT][PRT INT][END]"
    with pytest.raises(TimeoutError) as caught:
        vm.run_until_halt_or_all_branches_cycle(vm.make_vm("Modulous", source, "42\n"))
    assert str(caught.value) == (
        "undecided: a branching transition needs input that cannot be safely forked"
    )
    assert "seeded single-path run" in caught.value.__notes__[0]
    assert "does not decide all random paths" in caught.value.__notes__[0]
    assert esolangs.run("Modulous", source, stdin="42\n", seed=1, timeout=1) == "42"


@pytest.mark.medium
@pytest.mark.parametrize(
    ("language", "source"),
    [("Modulous", "[RND 257][END]"), ("Super SNUSP", '"999{>=')],
)
def test_larger_search_bounds_do_not_override_fixed_transition_caps(language, source):
    with pytest.raises(TimeoutError) as caught:
        vm.run_until_halt_or_all_branches_cycle(
            vm.make_vm(language, source), limit=100000
        )
    assert "cap on a single transition" in str(caught.value)
    assert "256" in caught.value.__notes__[0]
    assert "limit does not raise this transition cap" in caught.value.__notes__[0]


@pytest.mark.medium
def test_halt_and_cycle_verdicts_are_unchanged():
    assert vm.run_until_halt_or_cycle(vm.make_vm("brainfuck", "+."), limit=10) is True
    assert vm.run_until_halt_or_cycle(vm.make_vm("brainfuck", "+[]"), limit=10) is False
    assert (
        vm.run_until_halt_or_growth(vm.make_vm("brainfuck", "+[>+]"), limit=100)
        is False
    )
    assert (
        vm.run_until_halt_or_all_branches_cycle(vm.make_vm("Modulous", "[END]")) is True
    )
