"""Step observations count completed cooperative commands, never inferred work."""

import pytest

import esolangs
from esolangs.results import ExecutionResult
from esolangs.runtime._result_wire import decode_result, encode_result
from esolangs.vm import complete_vm, make_vm
from tests.support.pick import one_where
from tests.support.reference import REFERENCE

pytestmark = pytest.mark.medium


@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.parametrize("source", ["", "+[>+<-]>."])
def test_steps_match_an_independently_driven_machine(source, isolated):
    vm = make_vm(REFERENCE, source)
    steps = 0
    while not vm.halted:
        assert steps < 10000, "independent step control did not halt"
        vm.step()
        steps += 1
    native = esolangs.run(REFERENCE, source, isolated=isolated)
    bounded = esolangs.run(
        REFERENCE,
        source,
        isolated=isolated,
        limits=esolangs.ExecutionLimits(max_steps=steps),
    )
    assert native.output == bounded.output == vm.output
    assert native.steps is None
    assert bounded.steps == steps


@pytest.mark.parametrize("isolated", [False, True])
def test_zero_budget_performs_no_command(isolated):
    with pytest.raises(esolangs.ExecutionCapError) as caught:
        esolangs.run(
            REFERENCE,
            "+.",
            limits=esolangs.ExecutionLimits(max_steps=0),
            isolated=isolated,
        )
    assert caught.value.observation == ExecutionResult("", 0, 0, 0, steps=0)


@pytest.mark.parametrize("isolated", [False, True])
def test_final_dump_is_outside_the_command_budget(isolated):
    name = one_where(
        lambda info: info.answer_mode != "termination",
        boolean_generator=True,
        parameterized=True,
        dumps_on_the_post_halt_step=True,
        steppable_to_answer=True,
    )[0]
    source = esolangs.instantiate(name, esolangs.generate(name, "01"), [1])
    vm = make_vm(name, source)
    steps = 0
    while not vm.halted:
        assert steps < 10000, "independent step control did not halt"
        vm.step()
        steps += 1
    output = complete_vm(vm, max_steps=0)
    result = esolangs.run(
        name,
        source,
        limits=esolangs.ExecutionLimits(max_steps=steps),
        isolated=isolated,
    )
    assert result.steps == steps
    assert result.output == output
    assert esolangs.read_answer(name, result.output) == "1"


@pytest.mark.parametrize("steps", [-1, True, 1.5, "2"])
def test_worker_step_counter_requires_a_nonnegative_integer(steps):
    metadata = encode_result(ExecutionResult("output", 0, 0, 0))
    metadata["steps"] = steps
    with pytest.raises(ValueError, match="invalid execution counter"):
        decode_result("output", metadata)


def test_worker_requires_every_observation_field():
    result = ExecutionResult("output", None, None, None, steps=7)
    metadata = encode_result(result)
    assert decode_result(result.output, metadata) == result
    for key in (*metadata, "obsolete"):
        broken = (
            {**metadata, "obsolete": None}
            if key == "obsolete"
            else {k: value for k, value in metadata.items() if k != key}
        )
        with pytest.raises(ValueError, match="invalid execution result"):
            decode_result(result.output, broken)
