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
    {"limits": esolangs.ExecutionLimits(max_steps=10000)},
    {"isolated": True},
    {"isolated": True, "limits": esolangs.ExecutionLimits(max_steps=10000)},
]


def _stepped(route: dict) -> bool:
    """Whether ``route`` carries a step bound."""
    return "limits" in route and route["limits"].max_steps is not None


def _capped(route: dict) -> dict:
    """Return ``route`` with a one-character output cap added."""
    limits = route.get("limits", esolangs.ExecutionLimits())
    return route | {"limits": replace(limits, max_output=1)}


@pytest.mark.parametrize(
    "route", [*_ROUTES, *(_capped(r) for r in _ROUTES if r.get("isolated"))]
)
def test_result_counts_unicode_characters_and_preserves_unread_input(route):
    result = esolangs.run(REFERENCE, ",.", stdin="éNEXT", **route)
    assert result == ExecutionResult(
        "é",
        1,
        1,
        0,
        CompletionReport(Completion.HALTED),
        2 if _stepped(route) else None,
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
        lambda info: info.answer_mode != "termination",
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
    assert debugger.observation == native._replace(
        output="", completion=None, steps=end
    )
    assert native.output
    bounded = esolangs.run(
        name, source, stdin=stdin, limits=esolangs.ExecutionLimits(max_steps=end)
    )
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
                    native = run_observed(name, source, stdin=stdin, timeout=5)
                    assert esolangs.read_answer(name, native.output) == expected
                    _replay_periodic(name, source, stdin, native)
                    cases.append((name, source, stdin, native))
    assert len(cases) == 72
    for name in names:
        source = esolangs.ProgramArtifact("", name)
        native = run_observed(name, source, timeout=5)
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
    assert caught.value.observation == ExecutionResult(
        stdin,
        len(stdin),
        len(stdin),
        1,
        steps=2 * len(stdin) if _stepped(route) else None,
    )


def test_bound_language_returns_the_same_record():
    bound = esolangs.Language(REFERENCE)
    result = bound.run(
        ",.",
        stdin="éNEXT",
        limits=esolangs.ExecutionLimits(max_steps=2, max_output=1, execution_timeout=5),
        isolated=True,
    )
    assert result.steps == 2
    assert result._replace(steps=None) == esolangs.run(REFERENCE, ",.", stdin="éNEXT")


def test_public_record_is_immutable():
    from esolangs import debugger
    from esolangs.runtime import _vm_protocol

    assert esolangs.ExecutionResult is ExecutionResult
    assert debugger.VM is _vm_protocol.VM
    result = ExecutionResult("custom", None, None, None)
    assert result.completion is None
    assert pickle.loads(pickle.dumps(result)) == result
    with pytest.raises(AttributeError):
        result.output = "changed"
