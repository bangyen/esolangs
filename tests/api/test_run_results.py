"""Public results preserve output, input accounting and completion across routes."""

import pickle
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

import esolangs
from esolangs.debugger import make_debugger
from esolangs.registry import LANGUAGES
from esolangs.results import Completion, CompletionReport, ExecutionResult
from esolangs.runtime.io import ScriptedIO
from tests.support.certification_barrier import guarded_worker
from tests.support.execution import run_observed
from tests.support.pick import first, one_where
from tests.support.reference import REFERENCE

pytestmark = pytest.mark.medium
_ROUTES = [
    {},
    {"max_steps": 10000},
    {"isolated": True},
    {"isolated": True, "max_steps": 10000},
]


@pytest.mark.parametrize(
    "route", [*_ROUTES, *(r | {"max_output": 1} for r in _ROUTES if r.get("isolated"))]
)
def test_result_counts_unicode_characters_and_preserves_unread_input(route):
    result = esolangs.run(REFERENCE, ",.", stdin="éNEXT", **route)
    assert result == ExecutionResult(
        "é",
        1,
        1,
        0,
        CompletionReport(Completion.HALTED),
        2 if "max_steps" in route else None,
    )


@pytest.mark.parametrize("route", _ROUTES)
def test_result_retains_a_caught_eof(route):
    name = first(
        boolean_generator=True,
        parameterized=False,
        eof_is_a_value=True,
        source_kind="text",
        input_shape="char_stream",
    )
    source = esolangs.generate(name, "01")
    attempts = []

    class ObservedIO(ScriptedIO):
        def input_char(self, prompt="Input: "):
            try:
                return super().input_char(prompt)
            except EOFError:
                attempts.append(True)
                raise

    native = run_observed(name, source, io_factory=ObservedIO)
    assert (native.input_position, native.input_reads) == (0, 0)
    assert attempts, "the EOF control did not perform a read"
    assert native.input_past_end == len(attempts)
    assert esolangs.run(name, source, **route)._replace(steps=None) == native


@pytest.mark.parametrize(
    "name",
    one_where(
        lambda info: info["answer_mode"] != "termination",
        boolean_generator=True,
        dumps_on_the_post_halt_step=True,
        steppable_to_answer=True,
    ),
)
def test_post_halt_result_includes_the_final_dump(name):
    template = esolangs.generate(name, "01")
    source = (
        esolangs.instantiate(name, template, [1])
        if LANGUAGES[name].parameterized
        else template
    )
    stdin = "" if LANGUAGES[name].parameterized else esolangs.encode_inputs(name, [1])
    results = [esolangs.run(name, source, stdin=stdin, **route) for route in _ROUTES]
    assert all(result._replace(steps=None) == results[0] for result in results)
    assert results[1].steps == results[3].steps
    assert results[1].steps is not None
    assert results[0].completion.kind is Completion.POST_HALT
    assert results[0].completion.cycle is None
    assert esolangs.read_answer(name, results[0].output) == "1"
    if LANGUAGES[name].parameterized:
        assert results[0][1:4] == (0, 0, 0)


def _replay_periodic(name, source, stdin, native):
    assert native.completion.kind is Completion.PERIODIC
    cycle = native.completion.cycle
    assert cycle is not None
    debugger = make_debugger(name, source, stdin=stdin)
    end = cycle.repeat_pass * cycle.commands_per_pass
    first_command = cycle.first_pass * cycle.commands_per_pass
    first_state = None
    for command in range(end + 1):
        if command == first_command:
            first_state = debugger.snapshot()
        if command == end:
            break
        debugger.step()
    assert debugger.snapshot() == first_state == cycle.state
    assert not debugger.halted
    assert debugger.result == native._replace(output="", completion=None, steps=end)
    assert native.output
    bounded = esolangs.run(name, source, stdin=stdin, max_steps=end)
    assert bounded == native._replace(steps=end)


def test_periodic_result_retains_cycle_evidence_in_a_worker():
    names = [
        name
        for name, language in LANGUAGES.items()
        if language.runtime.capabilities.completion is Completion.PERIODIC
    ]
    assert len(names) == 1
    cases = []
    for name in names:
        for inputs in (1, 2):
            for mask in range(1 << (1 << inputs)):
                table = f"{mask:0{1 << inputs}b}"
                artifact = esolangs.generate(name, table)
                for row, expected in enumerate(table):
                    bits = [int(bit) for bit in f"{row:0{inputs}b}"]
                    source = (
                        esolangs.instantiate(name, artifact, bits)
                        if LANGUAGES[name].parameterized
                        else artifact
                    )
                    stdin = (
                        ""
                        if LANGUAGES[name].parameterized
                        else esolangs.encode_inputs(name, bits, truth_table=table)
                    )
                    native = esolangs.run(name, source, stdin=stdin, timeout=5)
                    assert esolangs.read_answer(name, native.output) == expected
                    _replay_periodic(name, source, stdin, native)
                    cases.append((name, source, stdin, native))
    assert len(cases) == 72
    for name in names:
        source = esolangs.ProgramArtifact("", name)
        native = esolangs.run(name, source, timeout=5)
        assert native.completion.cycle.commands_per_pass == 0
        _replay_periodic(name, source, "", native)
        cases.append((name, source, "", native))
    assert len(cases) == 73
    name, source, stdin, native = cases[-1]
    bad = native._replace(
        completion=replace(
            native.completion, cycle=replace(native.completion.cycle, state=("wrong",))
        )
    )
    with pytest.raises(AssertionError):
        _replay_periodic(name, source, stdin, bad)

    def check_worker(case):
        name, source, stdin, native = case
        assert esolangs.run(name, source, stdin=stdin, isolated=True) == native
        return name

    with guarded_worker(expected=len(cases)), ThreadPoolExecutor(max_workers=4) as pool:
        assert len(list(pool.map(check_worker, cases))) == len(cases)


@pytest.mark.parametrize("route", _ROUTES)
@pytest.mark.parametrize(("source", "stdin"), [(",", ""), (",.,", "é")])
def test_result_failures_still_raise_with_partial_output(route, source, stdin):
    with pytest.raises(esolangs.InputExhaustedError) as caught:
        esolangs.run(REFERENCE, source, stdin=stdin, **route)
    assert caught.value.partial_output == stdin
    assert caught.value.execution == ExecutionResult(
        stdin,
        len(stdin),
        len(stdin),
        1,
        steps=2 * len(stdin) if "max_steps" in route else None,
    )


def test_bound_language_returns_the_same_record():
    bound = esolangs.Language(REFERENCE)
    result = bound.run(
        ",.", stdin="éNEXT", max_steps=2, isolated=True, max_output=1, timeout=5
    )
    assert result.steps == 2
    assert result._replace(steps=None) == esolangs.run(REFERENCE, ",.", stdin="éNEXT")


def test_public_record_is_immutable_and_the_old_import_is_retired():
    from importlib import import_module

    assert esolangs.ExecutionResult is ExecutionResult
    assert not hasattr(esolangs, "run_result")
    assert not hasattr(esolangs.Language, "run_result")
    assert not hasattr(esolangs, "compat")
    assert not hasattr(esolangs, "_recover_template")
    for owner in (esolangs, esolangs.Language):
        assert not hasattr(owner, "generate_artifact")
        assert not hasattr(owner, "load_artifact")
    from esolangs import registry

    assert not hasattr(registry, "recover_setters")
    for retired in (
        "esolangs.runtime._result",
        "esolangs.compat",
        "esolangs.tagged",
        "esolangs.generation.raster_lookup",
    ):
        with pytest.raises(ModuleNotFoundError) as missing:
            import_module(retired)
        assert missing.value.name == retired
    from esolangs import _cycles, vm

    for retired in (
        "_AffineMachine",
        "_branch_search",
        "_BranchingStepMachine",
        "_checked_unwrap",
        "_clamps_hold",
        "_climbs_forever",
        "_FramedMachine",
        "_grows_forever",
        "_GrowthVisit",
        "_refuse_random",
        "_Snapshot",
        "_StepMachine",
        "_SteppableMachine",
        "_TapeMachine",
        "_unwrap",
        "_Visit",
    ):
        assert getattr(_cycles, retired) is not None
        assert not hasattr(vm, retired), retired
        with pytest.raises(ImportError, match=retired):
            exec(f"from esolangs.vm import {retired}", {})
    result = ExecutionResult("custom", None, None, None)
    assert result.completion is None
    assert pickle.loads(pickle.dumps(result)) == result
    with pytest.raises(AttributeError):
        result.output = "changed"
