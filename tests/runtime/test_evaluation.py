"""The private evaluation harness: supplied programs and budgets."""

import threading
from dataclasses import replace
from functools import partial
from io import StringIO
from pathlib import Path

import pytest

import esolangs
import tests.support.evaluation as evaluator
from tests.support.evaluation import _evaluate, _iter_evaluate, _row_answerer
from tests.support.generator_support import probe_table
from tests.support.pick import first, languages
from tests.support.reference import REFERENCE


def _kinds() -> list[str]:
    """One generator language per source kind, answer mode and input shape."""
    seen: dict[tuple, str] = {}
    for name in languages(boolean_generator=True):
        facts = esolangs.describe(name)
        key = (facts.source_kind, facts.answer_mode, facts.parameterized)
        seen.setdefault(key, name)
        seen.setdefault((facts.input_shape,), name)
    return sorted(set(seen.values()))


@pytest.mark.parametrize("name", _kinds())
@pytest.mark.parametrize("gzip", [False, True])
def test_evaluate_files(name: str, tmp_path: Path, *, gzip: bool) -> None:
    table = probe_table(name)
    program = esolangs.generate(name, table)
    path = tmp_path / "source"
    if gzip and esolangs.describe(name).source_kind == "raster":
        with pytest.raises(esolangs.ProgramError, match="rasters use PNG"):
            esolangs.to_file(name, program, path, gzip=True)
        assert not path.exists()
        return
    inputs = len(table).bit_length() - 1
    if isinstance(program, esolangs.TemplateArtifact):
        path.write_text(esolangs.to_json(name, program))
        restored = esolangs.from_json(name, path.read_text())
        assert _evaluate(name, restored, inputs=inputs) == table
        answer = _row_answerer(
            name,
            terminating=esolangs.describe(name).answer_mode == "termination",
            isolated=False,
            settings=program.settings,
            scale=None,
            max_output=None,
            max_memory=None,
        )
        for row, expected in enumerate(table):
            bits = [row >> shift & 1 for shift in reversed(range(inputs))]
            esolangs.to_file(
                name, esolangs.instantiate(name, restored, bits), path, gzip=gzip
            )
            loaded = esolangs.Language(name).from_file(
                path, settings=program.settings, normalize=True
            )
            assert answer(loaded, "", 30) == expected
        return
    esolangs.to_file(name, program, path, gzip=gzip)
    assert _evaluate(name, path, inputs=inputs) == table


@pytest.mark.parametrize("inputs", [True, 0, 65, 2.5, "2"])
def test_api_refuses_bad_inputs(inputs: object) -> None:
    with pytest.raises(esolangs.ArgumentError, match="inputs must"):
        _evaluate(REFERENCE, ",.", inputs=inputs)


def test_api_refuses_bad_source() -> None:
    with pytest.raises(esolangs.ProgramError, match="string of source"):
        _evaluate(REFERENCE, 42, inputs=1)


@pytest.mark.parametrize(
    "name",
    [first(source_kind="text", answer_mode=m) for m in ("output", "termination")],
)
def test_api_refuses_raster_for_text_answer(name: str) -> None:
    raster = esolangs.generate(first(source_kind="raster"), "0110").source
    with pytest.raises(esolangs.ProgramError, match="string of source"):
        _evaluate(name, raster, inputs=2)


def test_timeout_is_not_a_boolean_answer() -> None:
    with pytest.raises(esolangs.ExecutionTimeoutError) as exc:
        _evaluate(REFERENCE, "+[]", inputs=1, timeout=0.01)
    assert any("row 0" in note for note in exc.value.__notes__)


def test_answer_rejection_keeps_successful_execution_evidence() -> None:
    api = esolangs.Language(REFERENCE)
    program = api.from_source(",+.")
    result = api.run(program, stdin=api.encode_inputs([1]))
    assert result.output == "2"
    with pytest.raises(esolangs.ProgramError, match="no answer") as caught:
        api.evaluate(program, [1])
    assert caught.value.observation == result
    assert caught.value.partial_output == result.output


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"answer_mode": "termination"}, "invalid termination answer encoding"),
        ({"answer_mode": "unknown"}, "invalid answer mode"),
        ({"answer_values": ("1", "1")}, "invalid answer encoding"),
        ({"answer_values": ("1",)}, "invalid answer encoding"),
        ({"answer_pattern": "("}, "invalid answer pattern"),
    ],
)
def test_invalid_answer_contracts_stop_before_execution(
    monkeypatch, changes, message
) -> None:
    from esolangs.runtime import _execution, _isolated

    api = esolangs.Language(REFERENCE)
    declaration = api.catalog.languages[api.name]
    contract = replace(declaration.contract, **changes)
    scoped = esolangs.Catalog([replace(declaration, contract=contract)]).bind(api.name)
    artifact = scoped.from_source(",.")
    prepared = scoped.prepare(artifact)
    assert scoped.encode_inputs([0]) == "0"
    assert prepared.run(stdin="0").output == "0"

    def unexpected_execution(*_args, **_kwargs):
        pytest.fail("invalid answer contract started execution")

    monkeypatch.setattr(_execution, "invoke", unexpected_execution)
    monkeypatch.setattr(_isolated, "_invoke_worker", unexpected_execution)
    for evaluate in (
        partial(scoped.evaluate, artifact, [0]),
        partial(prepared.evaluate, [0]),
    ):
        for limits in (esolangs.ExecutionLimits(max_steps=4), None):
            with pytest.raises(esolangs.ProgramError, match=message) as caught:
                evaluate(limits=limits)
            assert caught.value.observation is None


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"input_shape": "unknown"}, "invalid input shape"),
        ({"alphabet": ("0",)}, "invalid input encoding"),
        ({"alphabet": (1, "1")}, "invalid input encoding"),
    ],
)
def test_input_contract_validation_does_not_affect_answer_decoding(
    changes, message
) -> None:
    api = esolangs.Language(REFERENCE)
    declaration = api.catalog.languages[api.name]
    contract = replace(declaration.contract, **changes)
    scoped = esolangs.Catalog([replace(declaration, contract=contract)]).bind(api.name)
    assert scoped.read_answer("1") == "1"
    with pytest.raises(esolangs.ProgramError, match=message):
        scoped.encode_inputs([1])
    with pytest.raises(esolangs.ProgramError, match=message):
        scoped.evaluate(scoped.from_source(",."), [1])


def test_reversed_termination_contract_uses_its_declared_bit_order() -> None:
    api = esolangs.Language(REFERENCE)
    declaration = api.catalog.languages[api.name]
    contract = replace(
        declaration.contract,
        answer_mode="termination",
        answer_values=("diverges", "halts"),
        answer_pattern="(",
    )
    scoped = esolangs.Catalog([replace(declaration, contract=contract)]).bind(api.name)
    limits = esolangs.ExecutionLimits(max_steps=5)
    for program, expected in (("[.]", "1"), ("+[]", "0")):
        artifact = scoped.from_source(program)
        assert scoped.evaluate(artifact, [0], limits=limits).answer == expected
        assert scoped.prepare(artifact).evaluate([0], limits=limits).answer == expected


def _termination_language(*, random: bool = False) -> esolangs.Language:
    api = esolangs.Language(REFERENCE)
    declaration = api.catalog.languages[api.name]
    contract = replace(
        declaration.contract,
        answer_mode="termination",
        answer_values=("halts", "diverges"),
    )
    runtime = (
        replace(declaration.runtime, random=True, reproducible_seed=4)
        if random
        else declaration.runtime
    )
    return esolangs.Catalog(
        [replace(declaration, contract=contract, runtime=runtime)]
    ).bind(api.name)


@pytest.mark.medium
@pytest.mark.parametrize(
    "deadline", [{}, {"total_timeout": 5}, {"preparation_timeout": 5}]
)
def test_termination_observes_completed_commands_and_loading_errors(deadline) -> None:
    api = _termination_language()
    limits = esolangs.ExecutionLimits(max_steps=2, **deadline)
    result = api.evaluate(api.from_source(",."), [0], limits=limits)
    completed = esolangs.ExecutionResult("0", 1, 1, 0, steps=2)
    assert result.answer == "0"
    assert result.termination.commands == 2
    assert result.observation == completed
    with pytest.raises(esolangs.ExecutionCapError) as stopped:
        api.evaluate(api.from_source(",.,"), [0], limits=limits)
    assert stopped.value.observation == completed
    with pytest.raises(esolangs.InputExhaustedError) as fault:
        api.evaluate(api.from_source(",.,"), [0], limits=replace(limits, max_steps=3))
    assert fault.value.observation == replace(completed, input_past_end=1)
    with pytest.raises(esolangs.ProgramError) as rejected:
        api.evaluate(api.from_source("["), [0], limits=limits)
    assert rejected.value.observation == esolangs.ExecutionResult("", 0, 0, 0)


def test_active_random_runtime_needs_branch_evidence(monkeypatch) -> None:
    from esolangs.runtime._execution import interpreter_module

    class RandomMachine:
        halted = False

        def __init__(self, rng):
            self.rng = rng

        def step(self):
            self.halted = self.rng.randbelow(2) == 1

        def snapshot(self):
            return ()

    def prepare(_source, options):
        return lambda _io: RandomMachine(options["rng"])

    api = _termination_language(random=True)
    runtime = api.catalog.languages[api.name].runtime
    monkeypatch.setattr(
        interpreter_module(api.name), runtime.machine_preparation, prepare
    )
    artifact = api.from_source("+.")
    vm = api.make_vm(artifact)
    initial = vm.snapshot()
    vm.step()
    assert vm.snapshot() == initial
    assert not vm.halted
    vm.step()
    assert vm.halted
    with pytest.raises(
        esolangs.InterpreterLimitError, match="requires branch enumeration"
    ) as caught:
        api.evaluate(artifact, [0], limits=esolangs.ExecutionLimits(max_steps=3))
    assert caught.value.observation == esolangs.ExecutionResult("", 0, 0, 0)


def test_evaluation_requires_unfilled_template_for_embedded_inputs() -> None:
    api = esolangs.Language(first(parameterized=True, answer_mode="output"))
    template = api.generate("01")
    filled = template.fill([1])
    assert api.read_answer(api.run(filled).output) == "1"
    for target in (filled, api.prepare(filled)):
        with pytest.raises(esolangs.ArgumentError, match="pass the unfilled template"):
            target.evaluate([0])


@pytest.mark.medium
@pytest.mark.parametrize("streaming", [False, True])
def test_isolated_row_output_limit_resets_per_row(streaming) -> None:
    source = "+" * 48 + "."
    evaluate = _iter_evaluate if streaming else _evaluate
    assert (
        "".join(evaluate(REFERENCE, source, inputs=1, isolated=True, max_output=1))
        == "00"
    )


@pytest.mark.medium
def test_evaluation_output_overflow_retains_partial_output_and_row() -> None:
    with pytest.raises(esolangs.ExecutionCapError, match="output limit") as caught:
        _evaluate(REFERENCE, "+" * 48 + "..", inputs=1, isolated=True, max_output=1)
    assert caught.value.partial_output == "0"
    assert any("row 0" in note for note in caught.value.__notes__)
    assert any("answered (none)" in note for note in caught.value.__notes__)


@pytest.mark.medium
def test_termination_output_limit_is_not_a_divergence_verdict() -> None:
    """A program that prints hits the limit; a silent one still answers."""
    outcomes = set()
    for name in languages(answer_mode="termination"):
        source = esolangs.generate(name, "01")
        try:
            answer = _evaluate(name, source, inputs=1, isolated=True, max_output=0)
        except esolangs.ExecutionCapError as error:
            outcomes.add(str(error).split(":")[0])
        else:
            assert answer == "01"
            outcomes.add("answer")
            decisions = [
                source.evaluate([bit], limits=esolangs.ExecutionLimits(max_steps=100))
                for bit in (0, 1)
            ]
            assert [result.answer for result in decisions] == ["0", "1"]
            assert {result.termination.halts for result in decisions} == {False, True}
            with pytest.raises(esolangs.ExecutionCapError) as stopped:
                source.evaluate([1], limits=esolangs.ExecutionLimits(max_steps=0))
            assert stopped.value.bound == "max_steps"
            assert stopped.value.observation is not None
    # Which termination languages print moves with the registry; each one
    # either answers or names the limit, never a divergence.
    assert "answer" in outcomes
    assert all(o == "answer" or "output limit" in o for o in outcomes), outcomes


@pytest.mark.parametrize("limit", [-1, True, 1.0])
def test_evaluation_rejects_invalid_output_limit_before_loading(
    limit, tmp_path
) -> None:
    with pytest.raises(esolangs.ArgumentError, match="max_output"):
        _evaluate(
            REFERENCE, tmp_path / "missing", inputs=1, isolated=True, max_output=limit
        )


def test_evaluation_output_limit_requires_isolation() -> None:
    with pytest.raises(esolangs.ArgumentError, match="isolated=True"):
        _evaluate(REFERENCE, "", inputs=1, max_output=1)


@pytest.mark.medium
@pytest.mark.parametrize("name", _kinds())
def test_streaming_executes_the_expected_table(name) -> None:
    table = probe_table(name)
    program = esolangs.generate(name, table)
    assert (
        "".join(_iter_evaluate(name, program, inputs=len(table).bit_length() - 1))
        == table
    )


def test_row_budget_refuses_before_loading() -> None:
    class Unreadable(StringIO):
        def read(self, *_args):
            pytest.fail("source must not load when the table exceeds its budget")

    with pytest.raises(esolangs.InterpreterLimitError, match="max_rows"):
        _evaluate(REFERENCE, Unreadable(), inputs=64)


@pytest.mark.parametrize("max_rows", [-1, True, 1.5])
def test_invalid_row_budgets(max_rows) -> None:
    with pytest.raises(esolangs.ArgumentError, match="max_rows"):
        _evaluate(REFERENCE, ",.", inputs=1, max_rows=max_rows)


@pytest.mark.medium
def test_row_budget_can_be_raised_or_disabled() -> None:
    for limit in (2, None):
        assert _evaluate(REFERENCE, ",.", inputs=1, max_rows=limit) == "01"
    with pytest.raises(esolangs.InterpreterLimitError):
        _evaluate(REFERENCE, ",.", inputs=1, max_rows=1)


@pytest.mark.medium
@pytest.mark.parametrize("isolated", [False, True])
def test_total_deadline_interrupts_source_acquisition(isolated) -> None:
    release = threading.Event()
    finished = threading.Event()

    class Blocked(StringIO):
        def read(self, *_args):
            try:
                release.wait(2)
                return ",."
            finally:
                finished.set()

    try:
        with pytest.raises(esolangs.ExecutionTimeoutError):
            _evaluate(
                REFERENCE, Blocked(), inputs=1, isolated=isolated, total_timeout=0.05
            )
    finally:
        release.set()
        assert finished.wait(2)


@pytest.mark.medium
def test_deadline_includes_iterator_pauses(monkeypatch) -> None:
    prepare = evaluator.prepare_program
    preparations = []

    def count_preparation(*args, **kwargs):
        preparations.append(args[1])
        return prepare(*args, **kwargs)

    monkeypatch.setattr(evaluator, "prepare_program", count_preparation)
    assert _evaluate(REFERENCE, ",.", inputs=1) == "01"
    assert len(preparations) == 1
    clock = [0.0]
    monkeypatch.setattr(evaluator, "monotonic", lambda: clock[0])
    answers = _iter_evaluate(REFERENCE, ",.", inputs=1, total_timeout=5)
    assert next(answers) == "0"
    clock[0] = 6
    with pytest.raises(
        esolangs.ExecutionTimeoutError, match="total deadline"
    ) as caught:
        next(answers)
    assert "row 1 of 2" in " ".join(caught.value.__notes__)


@pytest.mark.medium
def test_deadline_clamps_each_row_and_expires_after_work(monkeypatch) -> None:
    clock = [0.0]
    bounds = []
    monkeypatch.setattr(evaluator, "monotonic", lambda: clock[0])

    def run(_name, _source, stdin, timeout, **_options):
        bounds.append(timeout)
        clock[0] += 3
        return esolangs.ExecutionResult(stdin, None, None, None)

    monkeypatch.setattr("tests.support.execution.run_observed", run)
    with pytest.raises(esolangs.ExecutionTimeoutError):
        _evaluate(REFERENCE, ",.", inputs=1, timeout=None, total_timeout=5)
    assert bounds == [5, 2]


@pytest.mark.medium
@pytest.mark.parametrize("isolated", [False, True])
def test_total_deadline_bounds_a_growing_machine(isolated) -> None:
    with pytest.raises(esolangs.ExecutionTimeoutError):
        _evaluate(
            REFERENCE,
            "+[>+]",
            inputs=1,
            timeout=None,
            total_timeout=0.1,
            isolated=isolated,
        )


@pytest.mark.medium
@pytest.mark.parametrize("isolated", [False, True])
def test_loading_errors_keep_their_public_type_under_a_deadline(isolated) -> None:
    with pytest.raises(esolangs.ProgramError):
        _evaluate(REFERENCE, b"\xff", inputs=1, isolated=isolated, total_timeout=5)


@pytest.mark.parametrize("budget", [0, True, float("inf")])
def test_invalid_total_deadlines(budget) -> None:
    with pytest.raises(esolangs.ArgumentError):
        _evaluate(REFERENCE, ",.", inputs=1, total_timeout=budget)


def test_isolated_evaluation_requires_at_least_one_finite_budget() -> None:
    with pytest.raises(esolangs.ArgumentError, match="finite timeout"):
        _evaluate(REFERENCE, ",.", inputs=1, timeout=None, isolated=True)


@pytest.mark.parametrize("mode", ["output", "termination"])
@pytest.mark.parametrize(
    "error_type", [esolangs.HaltError, esolangs.ExecutionTimeoutError]
)
def test_execution_failure_never_becomes_an_answer(
    monkeypatch, mode, error_type
) -> None:
    name = first(boolean_generator=True, answer_mode=mode)
    program = esolangs.generate(name, "01")
    error = error_type("contract failure control")

    def fail(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(esolangs, "run", fail)
    monkeypatch.setattr("tests.support.execution.run_observed", fail)
    monkeypatch.setattr("esolangs.runtime._termination._halt_or_cycle_result", fail)
    with pytest.raises(error_type) as caught:
        _evaluate(name, program, inputs=1)
    assert caught.value is error
