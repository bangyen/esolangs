"""Reusable preparation must isolate source acquisition, state and randomness."""

from dataclasses import replace
from io import BytesIO
from types import ModuleType

import pytest

import esolangs
from esolangs.languages.brainfuck.interpreter import prepare_machine
from esolangs.registry import LANGUAGES
from esolangs.runtime._lifecycle import HALTED_REPORT
from esolangs.runtime._prepared import prepare_program
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import complete_vm
from tests.support.reference import REFERENCE


def _check_preparation_consumes_source_once_and_keeps_fresh_invocations():
    source = BytesIO(b",+.")
    prepared = esolangs.Language(REFERENCE).prepare(source)
    source.close()
    first, second = prepared.make_vm(stdin="A"), prepared.make_vm(stdin="Z")
    first.step()
    assert second.ip == 0
    assert complete_vm(first) == "B"
    assert complete_vm(second) == "["
    assert prepared.run(stdin="A").output == "B"
    bounded = prepared.run(stdin="Z", max_steps=3)
    assert bounded.output == "["
    assert bounded.input_position == bounded.input_reads == 1
    assert bounded.steps == 3
    assert prepared.run(stdin="A").output == "B"


def _check_prepared_isolation_preserves_the_same_observation():
    prepared = esolangs.Language(REFERENCE).prepare(",+.")
    assert prepared.run(stdin="A", isolated=True) == prepared.run(stdin="A")


def _check_prepared_failures_retain_partial_observations():
    prepared = esolangs.Language(REFERENCE).prepare(".,")
    for options in ({}, {"max_steps": 2}):
        with pytest.raises(esolangs.InputExhaustedError) as caught:
            prepared.run(**options)
        assert caught.value.partial_output == "\x00"
        observed = caught.value.execution
        assert observed.output == "\x00"
        assert observed.input_reads == 0
        assert observed.input_past_end == 1
        assert observed.completion is None


def _check_preparation_resets_seeded_randomness_for_each_invocation():
    declaration = LANGUAGES[REFERENCE]
    catalog = esolangs.Catalog(
        [replace(declaration, runtime=replace(declaration.runtime, random=True))]
    )
    module = ModuleType("prepared_random_control")
    draws = []

    def execute(_code, io, rng):
        values = tuple(rng.randbelow(256) for _ in range(8))
        draws.append(values)
        io.print_char(chr(values[0]))
        return HALTED_REPORT

    setattr(module, declaration.runtime.completion_entrypoint, execute)
    prepared = prepare_program(
        REFERENCE, "", catalog=catalog, module_loader=lambda *_a, **_k: module
    )
    assert prepared.run(seed=7) == prepared.run(seed=7)
    prepared.run(seed=8)
    assert draws[0] == draws[1] != draws[2]

    factories = []

    def prepare(_code, options):
        rng = options["rng"]
        factories.append(rng)
        return prepare_machine("+" * rng.randbelow(256) + ".", {})

    setattr(module, declaration.runtime.machine_preparation, prepare)
    first = complete_vm(prepared.make_vm(seed=7))
    second = complete_vm(prepared.make_vm(seed=7))
    third = complete_vm(prepared.make_vm(seed=8))
    assert first == second != third
    assert len(factories) == 3
    assert len({id(rng) for rng in factories}) == 3


def _check_prepared_factory_owns_state_and_input():
    factory = prepare_machine(",+.", {})
    first_io, second_io = ScriptedIO("A"), ScriptedIO("Z")
    first, second = factory(first_io), factory(second_io)
    before = second.snapshot()
    first.step()
    assert second.snapshot() == before
    assert second_io.progress() == 0
    while not first.halted:
        first.step()
    while not second.halted:
        second.step()
    assert first_io.getvalue() == "B"
    assert second_io.getvalue() == "["


@pytest.mark.medium
def test_prepared_invocations_own_source_state_and_randomness():
    _check_uniform_outcomes_and_phase_limits()
    _check_prepared_factory_owns_state_and_input()
    _check_preparation_consumes_source_once_and_keeps_fresh_invocations()
    _check_prepared_isolation_preserves_the_same_observation()
    _check_prepared_failures_retain_partial_observations()
    _check_preparation_resets_seeded_randomness_for_each_invocation()


def _check_uniform_outcomes_and_phase_limits():
    api = esolangs.Language(REFERENCE)
    for options in (
        {},
        {"limits": esolangs.ExecutionLimits(max_steps=10)},
        {"isolated": True},
    ):
        completed = api.execute(",+.", stdin="A", **options)
        assert completed.status == "completed"
        assert completed.unwrap().output == "B"
        assert completed.observation.input_position == 1
        failed = api.execute(".,", **options)
        assert failed.status == "input_exhausted"
        assert failed.observation.output == "\x00"
        assert failed.observation.input_past_end == 1
        assert failed.observation.completion is None
        with pytest.raises(esolangs.InputExhaustedError) as caught:
            failed.unwrap()
        assert caught.value is failed.error

    class Unread:
        def read(self):
            raise AssertionError("rejected options consumed stdin")

    for options in (
        {},
        {"limits": esolangs.ExecutionLimits(max_steps=10)},
        {"isolated": True},
    ):
        rejected = api.execute(",.", stdin=Unread(), seed=0, **options)
        assert rejected.status == "rejected"
        assert rejected.observation.completion is None
    prepared = api.prepare("+[]")
    stopped = prepared.execute(limits=esolangs.ExecutionLimits(max_steps=3))
    assert stopped.status == "limit"
    assert stopped.bound == "max_steps"
    assert stopped.observation.steps == 3
    for isolated in (False, True):
        stopped = prepared.execute(
            isolated=isolated,
            limits=esolangs.ExecutionLimits(
                execution_timeout=0.01, total_timeout=3 if isolated else None
            ),
        )
        assert stopped.status == "limit"
        assert stopped.bound == "execution_timeout"
        assert stopped.observation.completion is None
    stopped = prepared.execute(limits=esolangs.ExecutionLimits(total_timeout=0.02))
    assert stopped.status == "limit"
    assert stopped.bound == "total_timeout"
    rejected = api.execute("[")
    assert rejected.status == "rejected"
    assert rejected.observation.completion is None
    for kwargs in (
        {"max_steps": True},
        {"max_output": -1},
        {"max_memory": 0},
        {"total_timeout": float("inf")},
    ):
        with pytest.raises(esolangs.ArgumentError):
            esolangs.ExecutionLimits(**kwargs)
    with pytest.raises(esolangs.ArgumentError, match="completion evidence"):
        esolangs.ExecutionOutcome("completed", esolangs.ExecutionResult("", 0, 0, 0))
