"""Tests for the public package API."""

from concurrent.futures import ThreadPoolExecutor

import pytest

import esolangs
from esolangs import _check_program, debugger
from esolangs._evaluate import _evaluate
from esolangs._validate import check_bits, check_scale, check_timeout, check_whole
from esolangs.exceptions import EsolangError, UnknownLanguageError
from esolangs.interpreters.source_hints import error_text
from esolangs.registry import LANGUAGES
from esolangs.vm import machine_traits
from tests.stdin_check import _check_stdin


def test_list_languages() -> None:
    names = esolangs.list_languages()
    assert set(names) == set(LANGUAGES)
    assert names == sorted(names)


@pytest.mark.parametrize(
    "call",
    [
        lambda name: esolangs.generate(name, "x"),
        lambda name: esolangs.run(name, "x"),
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
    from esolangs.interpreters.io import ScriptedIO

    error = EsolangError("stop")

    def stop(
        _runner: object, _program: object, io: ScriptedIO, _timeout: object
    ) -> None:
        io.print_str("before")
        raise error

    monkeypatch.setattr(esolangs, "_run", stop)
    with pytest.raises(EsolangError) as caught:
        esolangs.run("brainfuck", "+")
    assert caught.value is error
    assert caught.value.partial_output == "before"
    assert caught.value.__notes__ == ["the program printed 'before' before this"]


def test_run_timeout_halts_runaway_program() -> None:
    """A program that never halts raises HaltError once the timeout elapses."""
    from esolangs.exceptions import HaltError

    with pytest.raises(HaltError, match="timeout"):
        esolangs.run("brainfuck", "+[]", timeout=0.1)


def test_run_timeout_halts_a_growing_program() -> None:
    """The signal interrupts a loop whose state never repeats."""
    with pytest.raises(esolangs.ExecutionTimeoutError, match="timeout"):
        esolangs.run("brainfuck", "+[>+]", timeout=0.01)


def test_run_timeout_requires_main_thread() -> None:
    """The SIGALRM guard needs a Unix main thread; elsewhere timeout is refused."""
    import threading

    out: list[BaseException | None] = [None]

    def runner() -> None:
        try:
            esolangs.run("brainfuck", "+", timeout=1)
        except BaseException as exc:
            out[0] = exc

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join(5)
    assert isinstance(out[0], ValueError)
    assert "SIGALRM" in str(out[0])


def test_describe_structured_summary() -> None:
    info = esolangs.describe("brainfuck")
    assert info["name"] == "brainfuck"
    assert info["state_model"] == "tape"
    assert info["boolean_generator"] is True
    assert info["wiki_url"] == "https://esolangs.org/wiki/brainfuck"


def test_describe_covers_state_models() -> None:
    models = {esolangs.describe(n)["state_model"] for n in esolangs.list_languages()}
    assert {"stack", "register", "grid", "tape"} <= models


@pytest.mark.parametrize("table", ["", "0120", "010", "1"])
def test_truth_table_hint(table: str) -> None:
    with pytest.raises(esolangs.TruthTableError) as caught:
        esolangs.generate("brainfuck", table)
    assert caught.value.__notes__[0].startswith("hint:")
    assert error_text(caught.value).startswith(str(caught.value) + "\nhint:")


@pytest.mark.parametrize("table", ["00", "11"])
def test_truth_table_examples_execute(table: str) -> None:
    program = esolangs.generate("brainfuck", table)
    inputs = len(table).bit_length() - 1
    for row, expected in enumerate(table):
        bits = [(row >> shift) & 1 for shift in reversed(range(inputs))]
        output = esolangs.run(
            "brainfuck", program, stdin=esolangs.encode_inputs("brainfuck", bits)
        )
        assert esolangs.read_answer("brainfuck", output) == expected


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


def test_debugger_exports_are_available():
    for name in debugger.__all__:
        assert hasattr(debugger, name)
    assert debugger.make_vm("brainfuck", "+.").ip == 0
    assert debugger.make_debugger("brainfuck", "+.").run() == "halted"


@pytest.mark.medium  # spawns a worker, like test_run_isolated
def test_isolated_execution_loads_a_path_in_worker_thread(tmp_path):
    path = tmp_path / "program.bf"
    path.write_text("++.")
    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(esolangs.run, "brainfuck", path, isolated=True)
        assert result.result(timeout=5) == "\x02"


@pytest.mark.parametrize(
    "options",
    [
        {"isolated": True, "max_steps": 2},
        {"max_steps": 2, "seed": 1},
    ],
)
def test_unsupported_execution_options_are_refused(options):
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run("brainfuck", "+.", **options)


def test_isolated_seed_is_forwarded(monkeypatch):
    seen = []

    def execute(language, program, stdin, timeout, *, seed):
        seen.append((language, program, stdin, timeout, seed))
        return "result"

    monkeypatch.setattr(esolangs, "_run_isolated", execute)
    assert esolangs.run("brainfuck", "+.", isolated=True, seed=7) == "result"
    assert seen == [("brainfuck", "+.", "", 30.0, 7)]


def test_runnable_guard_refuses_non_source_values():
    from esolangs import _check_runnable

    with pytest.raises(esolangs.ProgramError, match="got int"):
        _check_runnable("brainfuck", 7)


def test_default_answer_contract_reads_the_final_bit():
    assert esolangs.read_answer("brainfuck", "answer: 1\n") == "1"


def test_isolated_worker_requires_a_deadline():
    from esolangs import _isolated

    with pytest.raises(esolangs.ArgumentError, match="finite timeout"):
        _isolated.run_isolated("brainfuck", "+.", timeout=None)


def test_bound_language_runs_a_boolean_workflow():
    language = esolangs.Language(" BRAINFUCK ")
    assert language.name == "brainfuck"
    assert language.describe()["name"] == language.name
    program = language.generate("0110", balance=True)
    stdin = language.encode_inputs([0, 1], truth_table="0110")
    _check_stdin(language.name, stdin, "0110")
    assert _check_program(language.name, program, stdin) == program
    assert language.read_answer(language.run(program, stdin=stdin)) == "1"
    assert _evaluate(language.name, program, inputs=2) == "0110"


@pytest.mark.medium
def test_bound_language_preserves_subprocess_defaults_on_a_worker(tmp_path):
    language = esolangs.Language("brainfuck")
    path = tmp_path / "program.bf"
    path.write_text("++.")
    with ThreadPoolExecutor(max_workers=1) as pool:
        output = pool.submit(language.run, path, isolated=True)
        assert output.result(timeout=5) == "\x02"
        table = pool.submit(_evaluate, language.name, ",.", inputs=1, isolated=True)
        assert table.result(timeout=5) == "01"
    # None is the public default, so under isolation it is the 30-second
    # deadline rather than a refusal.
    assert language.run(path, isolated=True, timeout=None) == "\x02"


def test_bound_execution_keeps_partial_output_on_step_exhaustion():
    language = esolangs.Language("brainfuck")
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        language.run("+.[]", max_steps=10, timeout=1)
    assert caught.value.partial_output == "\x01"
