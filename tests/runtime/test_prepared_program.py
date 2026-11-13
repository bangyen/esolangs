"""Reusable preparation must isolate source acquisition, state and randomness."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO
from types import ModuleType
from unittest.mock import patch

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
    bounded = prepared.run(stdin="Z", limits=esolangs.ExecutionLimits(max_steps=3))
    assert bounded.output == "["
    assert bounded.input_position == bounded.input_reads == 1
    assert bounded.steps == 3
    assert prepared.run(stdin="A").output == "B"

    language = esolangs.Language(REFERENCE)
    with pytest.raises(esolangs.ProgramError, match="program or template artifact"):
        language.evaluate(",.", [0])
    generated = language.prepare(esolangs.generate(REFERENCE, "0110"))
    with pytest.raises(
        esolangs.ArgumentError, match="has 2 inputs, but 1 bit was given"
    ):
        generated.evaluate([0])
    assert generated.evaluate([0, 1]).bit == "1"
    assert generated.evaluate([1, 1]).bit == "0"


def _check_prepared_isolation_preserves_the_same_observation():
    prepared = esolangs.Language(REFERENCE).prepare(",+.")
    assert prepared.run(stdin="A", isolated=True) == prepared.run(stdin="A")


def _check_prepared_failures_retain_partial_observations():
    prepared = esolangs.Language(REFERENCE).prepare(".,")
    for options in ({}, {"limits": esolangs.ExecutionLimits(max_steps=2)}):
        with pytest.raises(esolangs.InputExhaustedError) as caught:
            prepared.run(**options)
        assert caught.value.partial_output == "\x00"
        observed = caught.value.observation
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


def _check_prepared_source_options_and_lines_are_reused():
    from esolangs._dialect import DialectSchema
    from esolangs.runtime._definition import LineSourcePolicy

    declaration = LANGUAGES[REFERENCE]
    schema = DialectSchema(declaration.name, {"increment": (1, 2)}, {"increment": 1})
    validated = []

    def validate(increment=1):
        validated.append(increment)

    runtime = replace(
        declaration.runtime,
        source_policy=LineSourcePolicy(),
        dialect=validate,
        dialect_schema=schema,
    )
    catalog = esolangs.Catalog([replace(declaration, runtime=runtime)])
    module = ModuleType("prepared_source_control")

    def execute(lines, io, increment):
        assert lines.pop() == "last"
        io.print_str(lines.pop() * increment)
        return HALTED_REPORT

    setattr(module, runtime.completion_entrypoint, execute)
    api = esolangs.Language(REFERENCE, catalog=catalog)
    prepared = prepare_program(
        REFERENCE,
        "first\r\nlast\r\n",
        settings=api.settings(increment=2),
        catalog=catalog,
        module_loader=lambda *_args, **_kwargs: module,
    )
    assert validated
    validated.clear()
    assert prepared.run().output == "firstfirst"
    assert prepared.run().output == "firstfirst"
    assert validated == []


@pytest.mark.medium
def test_prepared_invocations_own_source_state_and_randomness(monkeypatch):
    _check_uniform_outcomes_and_phase_limits()
    with monkeypatch.context() as patch:
        _check_preparation_timeout(patch)
    _check_outcomes_are_the_internal_boundary(monkeypatch)
    _check_prepared_factory_owns_state_and_input()
    _check_prepared_source_options_and_lines_are_reused()
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
    from esolangs.operations import execution

    with patch.object(
        execution, "_execute_isolated", wraps=execution._execute_isolated
    ) as worker:
        stopped = prepared.execute(
            limits=esolangs.ExecutionLimits(max_steps=3, execution_timeout=3),
        )
    assert worker.call_args is not None
    assert worker.call_args.kwargs["execution_timeout"] == 3
    assert worker.call_args.kwargs["max_steps"] == 3
    assert stopped.status == "limit"
    assert stopped.bound == "max_steps"
    assert stopped.observation.steps == 3
    stopped = prepared.execute(
        limits=esolangs.ExecutionLimits(max_steps=10**9, execution_timeout=0.01),
    )
    assert stopped.status == "limit"
    assert stopped.bound == "execution_timeout"
    assert stopped.observation.completion is None
    with ThreadPoolExecutor(max_workers=1) as threads:
        stopped = threads.submit(
            prepared.execute,
            limits=esolangs.ExecutionLimits(execution_timeout=0.01, total_timeout=3),
        ).result(timeout=5)
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
        {"max_memory": -1},
        {"total_timeout": float("inf")},
        {"execution_timeout": 0},
        {"preparation_timeout": 0},
    ):
        # Each names its own field; all three timeouts said "timeout".
        with pytest.raises(esolangs.ArgumentError, match=f"^{next(iter(kwargs))} "):
            esolangs.ExecutionLimits(**kwargs)
    # run said "non-negative" for -1 while refusing 0.
    with pytest.raises(esolangs.ArgumentError, match="max_memory must be a positive"):
        esolangs.run(
            REFERENCE,
            "+",
            isolated=True,
            limits=esolangs.ExecutionLimits(max_memory=-1),
        )
    with pytest.raises(esolangs.ArgumentError, match="completion evidence"):
        esolangs.ExecutionOutcome("completed", esolangs.ExecutionResult("", 0, 0, 0))


def _check_preparation_timeout(monkeypatch):
    from threading import Event

    from esolangs.runtime import _isolated

    api = esolangs.Language(REFERENCE)
    phase_limits = esolangs.ExecutionLimits(preparation_timeout=1, total_timeout=4)
    for steps in (None, 10):
        limits = replace(phase_limits, max_steps=steps)
        assert api.execute(",+.", stdin="A", limits=limits).unwrap().output == "B"
    prepared = api.prepare(",+.")
    tiny_budget = esolangs.ExecutionLimits(preparation_timeout=0.001)
    assert prepared.execute(stdin="A", limits=tiny_budget).unwrap().output == "B"

    release = Event()

    class Blocked:
        def read(self):
            release.wait()
            return "+."

    try:
        stopped = api.execute(Blocked(), limits=tiny_budget)
    finally:
        release.set()
    assert stopped.bound == "preparation_timeout"
    assert stopped.observation.steps is None

    spawn = _isolated.subprocess.Popen
    children = []

    def slow_parser(argv, **options):
        patch = (
            "from time import sleep; "
            "from esolangs.runtime import _prepared; "
            "_prepared.prepare_program = lambda *a, **kw: sleep(10); "
        )
        child = spawn([*argv[:-1], patch + argv[-1]], **options)
        children.append(child)
        return child

    monkeypatch.setattr(_isolated.subprocess, "Popen", slow_parser)
    stopped = api.execute("+.", limits=phase_limits)
    assert stopped.bound == "preparation_timeout"
    assert stopped.observation.output == ""
    assert len(children) == 1
    assert children[0].poll() is not None
    stopped = api.execute("+.", limits=replace(phase_limits, total_timeout=0.1))
    assert stopped.bound == "total_timeout"


def _check_outcomes_are_the_internal_boundary(monkeypatch):
    from esolangs.operations import execution
    from esolangs.runtime import _isolated

    def refuse_legacy_run(*_args, **_kwargs):
        raise AssertionError("execute used the raising result adapter")

    with monkeypatch.context() as patch:
        patch.setattr(execution, "run", refuse_legacy_run)
        api = esolangs.Language(REFERENCE)
        for options in ({}, {"limits": esolangs.ExecutionLimits(max_steps=10)}):
            assert api.execute(",+.", stdin="A", **options).unwrap().output == "B"
            assert api.execute(".,", **options).status == "input_exhausted"
        # The real worker runs the same primitive; direct serving is covered
        # by the worker protocol tests, without this parent's monkeypatches.
        assert api.execute(",+.", stdin="A", isolated=True).unwrap().output == "B"

    fault = esolangs.HaltError("same fault", hint="retain this note")
    observed = esolangs.ExecutionResult("prefix", 1, 1, 0, steps=2)
    fault.observation, fault.partial_output = observed, observed.output
    from esolangs.outcomes import _failed_outcome

    failed = _failed_outcome(fault)
    assert failed.error is fault
    assert failed.observation is observed
    assert failed.status == "fault"
    with pytest.raises(esolangs.HaltError) as caught:
        failed.unwrap()
    assert caught.value is fault
    assert "retain this note" in fault.__notes__[0]
    response = _isolated._decode_outcome('{"output":"prefix"}\n', expired=True)
    assert response.status == "limit"
    assert response.observation == esolangs.ExecutionResult("prefix", None, None, None)
    assert response.observation.completion is None
    assert response.error.observation is None


@pytest.mark.medium
def test_an_execution_budget_outlasts_the_default_total() -> None:
    """``run(timeout=33)`` stopped at the flat 30-second total, worded "30.0"."""
    from esolangs.operations import execution

    with patch.object(execution, "_ISOLATED_TIMEOUT", 3.0):
        stopped = esolangs.Language(REFERENCE).execute(
            "+[]", limits=esolangs.ExecutionLimits(execution_timeout=4.0)
        )
        assert stopped.bound == "execution_timeout"
        with pytest.raises(esolangs.ExecutionTimeoutError, match=r"4\.0-second") as e:
            esolangs.run(
                REFERENCE,
                "+[]",
                limits=esolangs.ExecutionLimits(execution_timeout=4.0),
                isolated=True,
            )
        assert e.value.bound == "execution_timeout"
        # The default total said "timeout", a parameter never passed.
        with pytest.raises(esolangs.ExecutionTimeoutError) as e:
            esolangs.run(REFERENCE, "+[]", isolated=True)
        assert e.value.bound == "total_timeout"
    # PreparedProgram.run passed timeout as the whole-call deadline, in process:
    # this never stopped.
    stuck = esolangs.Language(REFERENCE).prepare("+[]")
    with pytest.raises(esolangs.ExecutionTimeoutError, match=r"1\.0-second") as e:
        stuck.run(limits=esolangs.ExecutionLimits(execution_timeout=1.0))
    assert e.value.bound == "execution_timeout"
