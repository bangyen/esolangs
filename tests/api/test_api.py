"""Tests for the public package API."""

from concurrent.futures import ThreadPoolExecutor

import pytest

import esolangs
import esolangs.operations.execution as _execution_operations
import esolangs.runtime._execution as _execution_runtime
from esolangs import debugger
from esolangs.exceptions import EsolangError, UnknownLanguageError
from esolangs.operations.source import _check_program
from esolangs.registry import LANGUAGES
from esolangs.runtime._capabilities import MachineCapabilities
from esolangs.runtime._context import ExecutionContext
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._validate import (
    check_bits,
    check_scale,
    check_timeout,
    check_whole,
)
from esolangs.runtime.source_hints import error_text
from esolangs.vm import machine_traits
from tests.support.evaluation import _evaluate
from tests.support.reference import REFERENCE


def test_list_languages() -> None:
    names = esolangs.list_languages()
    assert set(names) == set(LANGUAGES)
    assert names == sorted(names)


def test_seed_hint_tracks_registered_random_languages() -> None:
    from esolangs.registry import Language
    from esolangs.runtime import _execution

    registered = {
        REFERENCE: LANGUAGES[REFERENCE],
        "Draws": Language(
            "Draws",
            RuntimeSpec(
                "draws",
                machine_preparation="prepare_machine",
                completion_entrypoint="_execute",
                capabilities=MachineCapabilities(),
                random=True,
            ),
        ),
        "Quiet": Language(
            "Quiet",
            RuntimeSpec(
                "quiet",
                machine_preparation="prepare_machine",
                completion_entrypoint="_execute",
                capabilities=MachineCapabilities(),
            ),
        ),
    }
    catalog = esolangs.Catalog(registered.values())
    with pytest.raises(
        esolangs.ArgumentError, match="the languages that draw are Draws"
    ):
        _execution.prepare_call(
            REFERENCE, "", ExecutionContext(seed=1), catalog=catalog
        )
    del registered["Draws"]
    catalog = esolangs.Catalog(registered.values())
    with pytest.raises(esolangs.ArgumentError, match="no registered language draws"):
        _execution.prepare_call(
            REFERENCE, "", ExecutionContext(seed=1), catalog=catalog
        )


@pytest.mark.parametrize(
    "call",
    [
        lambda name: esolangs.generate(name, "x"),
        lambda name: esolangs.run(name, "x").output,
        lambda name: debugger.make_debugger(name, "+"),
        # Naming the language it refused is the whole use of the message to
        # a caller who passed it by mistake.
        lambda name: debugger.make_vm(name, "+"),
        machine_traits,
    ],
    ids=["generate", "run", "make_debugger", "make_vm", "machine_traits"],
)
def test_unknown_language_raises(call) -> None:
    with pytest.raises(UnknownLanguageError, match="NoSuchLanguage"):
        call("NoSuchLanguage")


def test_unknown_language_error_is_catchable() -> None:
    assert issubclass(UnknownLanguageError, EsolangError)
    assert issubclass(UnknownLanguageError, ValueError)


def test_missing_dependency_error_is_public() -> None:
    assert issubclass(esolangs.MissingDependencyError, EsolangError)
    assert issubclass(esolangs.MissingDependencyError, ImportError)


def test_deliberate_error_keeps_partial_output(monkeypatch: pytest.MonkeyPatch) -> None:
    from esolangs.runtime.io import ScriptedIO

    error = EsolangError("stop")

    def stop(_runner: object, _program: object, io: ScriptedIO) -> None:
        io.print_str("before")
        raise error

    monkeypatch.setattr(_execution_runtime, "invoke", stop)
    with pytest.raises(EsolangError) as caught:
        esolangs.run(REFERENCE, "+")
    assert caught.value is error
    assert caught.value.partial_output == "before"
    assert caught.value.__notes__ == ["the program printed 'before' before this"]


def test_run_timeout_halts_runaway_program() -> None:
    """A program that never halts raises HaltError once the timeout elapses."""
    from esolangs.exceptions import HaltError

    with pytest.raises(HaltError, match="timeout"):
        esolangs.run(
            REFERENCE, "+[]", limits=esolangs.ExecutionLimits(execution_timeout=0.1)
        )


def test_run_timeout_halts_a_growing_program() -> None:
    """The deadline interrupts a loop whose state never repeats."""
    with pytest.raises(esolangs.ExecutionTimeoutError, match="timeout"):
        esolangs.run(
            REFERENCE, "+[>+]", limits=esolangs.ExecutionLimits(execution_timeout=0.01)
        )


def test_run_timeout_works_off_main_thread(monkeypatch) -> None:
    """Timed runs use a worker without changing the parent's signals."""
    import concurrent.futures
    import signal

    def forbidden(*_args):
        raise AssertionError("timed run changed a parent signal handler")

    monkeypatch.setattr(signal, "signal", forbidden)
    with concurrent.futures.ThreadPoolExecutor() as pool:
        result = pool.submit(
            esolangs.run,
            REFERENCE,
            "+.",
            limits=esolangs.ExecutionLimits(execution_timeout=5),
        ).result(10)
    assert result.output == "\x01"


def test_a_timeout_names_the_bound_that_fired() -> None:
    """Both bounds raise one class; ``bound`` separates them, pickled too."""
    import pickle

    with pytest.raises(esolangs.ExecutionCapError) as stepped:
        esolangs.run(
            REFERENCE,
            "+[]",
            limits=esolangs.ExecutionLimits(max_steps=100, execution_timeout=30),
        )
    with pytest.raises(esolangs.ExecutionTimeoutError) as timed:
        esolangs.run(
            REFERENCE, "+[]", limits=esolangs.ExecutionLimits(execution_timeout=0.05)
        )
    with pytest.raises(esolangs.ExecutionTimeoutError) as combined:
        esolangs.run(
            REFERENCE,
            "+[]",
            limits=esolangs.ExecutionLimits(max_steps=10**9, execution_timeout=0.01),
        )
    assert combined.value.bound == "execution_timeout"
    for caught, bound in ((stepped, "max_steps"), (timed, "execution_timeout")):
        assert caught.value.bound == bound
        assert pickle.loads(pickle.dumps(caught.value)).bound == bound


def test_describe_structured_summary() -> None:
    info = esolangs.describe(REFERENCE)
    assert info.name == REFERENCE
    assert info.state_model == "tape"
    assert info.generator_shape == "tree"
    assert info.boolean_generator is True
    assert info.wiki_url == "https://esolangs.org/wiki/brainfuck"


def test_describe_covers_state_models() -> None:
    models = {esolangs.describe(n).state_model for n in esolangs.list_languages()}
    assert {"stack", "register", "grid", "tape"} <= models


def test_input_fields_exist_only_where_stdin_is_read() -> None:
    """Templates and interpreter-only languages reported ``line_per_bit``."""
    for name in esolangs.list_languages():
        facts = esolangs.describe(name)
        has_input = facts.input_shape is not None
        assert has_input is facts.reads_input, name
        assert (facts.input_encoding is not None) is has_input, name
        if not facts.boolean_generator:
            with pytest.raises(esolangs.ArgumentError, match="reads no stdin"):
                esolangs.encode_inputs(name, [1])


def test_shape_is_the_generator_axis() -> None:
    """A generator reports its construction shape; no generator means None."""
    for name in esolangs.list_languages():
        facts = esolangs.describe(name)
        if facts.boolean_generator:
            assert facts.generator_shape in {"tree", "reducing", "lookup"}, name
        else:
            assert facts.generator_shape is None, name
    shapes = {
        esolangs.describe(n).generator_shape
        for n in esolangs.list_languages()
        if esolangs.describe(n).boolean_generator
    }
    assert shapes == {"tree", "reducing", "lookup"}


@pytest.mark.parametrize("table", ["", "0120", "010", "1"])
def test_truth_table_hint(table: str) -> None:
    with pytest.raises(esolangs.TruthTableError) as caught:
        esolangs.generate(REFERENCE, table)
    assert caught.value.__notes__[0].startswith("hint:")
    assert error_text(caught.value).startswith(str(caught.value) + "\nhint:")


@pytest.mark.parametrize("table", ["00", "11"])
def test_truth_table_examples_execute(table: str) -> None:
    program = esolangs.generate(REFERENCE, table)
    inputs = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        bits = [(row >> shift) & 1 for shift in reversed(range(inputs))]
        output = esolangs.run(
            REFERENCE, program, stdin=esolangs.encode_inputs(REFERENCE, bits)
        ).output
        assert esolangs.read_answer(REFERENCE, output) == expected


def test_option_hints_preserve_messages() -> None:
    with pytest.raises(esolangs.ArgumentError) as caught:
        check_whole(-1, "max_steps")
    assert str(caught.value) == "max_steps must be a non-negative integer, got -1"
    assert "max_steps=0" in caught.value.__notes__[0]
    for check, value, example in (
        (check_timeout, 0, "timeout=5.0"),
        (check_scale, 0, "scale=1"),
        (check_bits, [], "[0, 1]"),
    ):
        with pytest.raises(esolangs.ArgumentError) as caught:
            check(value)
        assert example in caught.value.__notes__[0]
    check_timeout(5.0)
    assert check_whole(0, "max_steps") == 0
    assert check_scale(1) == 1
    assert check_bits([0, 1]) == [0, 1]


def test_debugger_exports_are_available() -> None:
    for name in debugger.__all__:
        assert hasattr(debugger, name)
    assert debugger.make_vm(REFERENCE, "+.").ip == 0
    assert debugger.make_debugger(REFERENCE, "+.").run() == "halted"


@pytest.mark.medium  # spawns a worker, like test_run_isolated
def test_isolated_execution_loads_a_path_in_worker_thread(tmp_path) -> None:
    path = tmp_path / "program.bf"
    path.write_text("++.")
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(esolangs.run, REFERENCE, path, isolated=True)
        assert result.result(timeout=5).output == "\x02"


def test_isolated_seed_is_forwarded(monkeypatch) -> None:
    from esolangs.results import ExecutionResult
    from esolangs.runtime._lifecycle import HALTED_REPORT

    seen = []

    def execute(language, program, stdin, timeout, **kwargs):
        seen.append((language, program, stdin, timeout, kwargs))
        return esolangs.ExecutionOutcome(
            "completed", ExecutionResult("result", 0, 0, 0, HALTED_REPORT)
        )

    monkeypatch.setattr(_execution_operations, "_execute_isolated", execute)
    name = next(name for name, lang in LANGUAGES.items() if lang.runtime.random)
    assert esolangs.run(name, "+.", isolated=True, seed=7).output == "result"
    ((language, program, stdin, timeout, kwargs),) = seen
    assert (language, program, stdin, timeout) == (name, "+.", "", 30.0)
    assert kwargs["seed"] == 7


def test_runnable_guard_refuses_non_source_values() -> None:
    from esolangs.operations.source import _check_program

    with pytest.raises(esolangs.ProgramError, match="got int"):
        _check_program(REFERENCE, 7)


def test_default_answer_contract_reads_the_final_bit() -> None:
    assert esolangs.read_answer(REFERENCE, "answer: 1\n") == "1"


def test_isolated_worker_requires_a_deadline() -> None:
    from esolangs.runtime import _isolated

    with pytest.raises(esolangs.ArgumentError, match="finite timeout"):
        _isolated.execute_isolated(REFERENCE, "+.", timeout=None).unwrap()


def test_bound_language_runs_a_boolean_workflow() -> None:
    language = esolangs.Language(" BRAINFUCK ")
    assert language.name == REFERENCE
    assert language.describe().name == language.name
    program = language.generate("0110", balance=True)
    stdin = language.encode_inputs([0, 1], truth_table="0110")
    assert _check_program(language.name, program, stdin).source == program.source
    assert language.read_answer(language.run(program, stdin=stdin).output) == "1"
    assert _evaluate(language.name, program, inputs=2) == "0110"


@pytest.mark.medium
def test_bound_language_preserves_subprocess_defaults_on_a_worker(tmp_path) -> None:
    language = esolangs.Language(REFERENCE)
    path = tmp_path / "program.bf"
    path.write_text("++.")
    with ThreadPoolExecutor(max_workers=1) as pool:
        output = pool.submit(language.run, path, isolated=True)
        assert output.result(timeout=5).output == "\x02"
        table = pool.submit(_evaluate, language.name, ",.", inputs=1, isolated=True)
        assert table.result(timeout=5) == "01"
    # None is the public default, so under isolation it is the 30-second
    # deadline rather than a refusal.
    assert (
        language.run(
            path, isolated=True, limits=esolangs.ExecutionLimits(execution_timeout=None)
        ).output
        == "\x02"
    )


def test_bound_execution_keeps_partial_output_on_step_exhaustion() -> None:
    language = esolangs.Language(REFERENCE)
    with pytest.raises(esolangs.ExecutionCapError) as caught:
        language.run(
            "+.[]",
            limits=esolangs.ExecutionLimits(max_steps=10, execution_timeout=1),
        )
    assert caught.value.partial_output == "\x01"
