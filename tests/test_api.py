"""Tests for the public package API."""

import warnings
from concurrent.futures import ThreadPoolExecutor

import pytest

import esolangs
from esolangs import _check_program, debugger
from esolangs import tools as boolean
from esolangs._evaluate import _evaluate
from esolangs._validate import check_bits, check_scale, check_timeout, check_whole
from esolangs.exceptions import EsolangError, UnknownLanguageError
from esolangs.interpreters.source_hints import error_text
from tests.stdin_check import _check_stdin


def test_list_languages() -> None:
    names = esolangs.list_languages()
    assert "Sophie" in names
    assert "Circlefuck" in names
    assert names == sorted(names)


def test_unknown_language_raises() -> None:
    with pytest.raises(UnknownLanguageError):
        esolangs.generate("NoSuchLanguage", "x")
    with pytest.raises(UnknownLanguageError):
        esolangs.run("NoSuchLanguage", "x")
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


def test_run_warns_when_input_runs_out() -> None:
    program = boolean.circlefuck("10")  # reads one input bit
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        esolangs.run("Circlefuck", program, stdin="")


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
    assert esolangs.describe("Forþ")["state_model"] == "stack"
    assert esolangs.describe("Decleq")["state_model"] == "register"
    assert esolangs.describe("LaserFuck")["state_model"] == "grid"
    assert esolangs.describe("NoComment")["boolean_generator"] is True


def test_generate_refuses_a_language_with_no_generator() -> None:
    """A registered language may have no generator, and must say so."""
    with pytest.raises(esolangs.ArgumentError) as exc:
        esolangs.generate("Deadfish", "0110")
    message = str(exc.value)
    assert "no boolean generator" in message
    assert "generator contracts" in message
    assert "'int'" in message


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


def test_template_hint_and_example() -> None:
    template = esolangs.generate("Minifuck", "0110")
    with pytest.raises(esolangs.TemplateError) as caught:
        esolangs.instantiate("Minifuck", template, [0])
    assert "exactly 2 integer bits" in caught.value.__notes__[0]
    program = esolangs.instantiate("Minifuck", template, [0, 1])
    assert esolangs.read_answer("Minifuck", esolangs.run("Minifuck", program)) == "1"


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


def test_generator_cap_hint() -> None:
    with pytest.raises(esolangs.GeneratorCapError) as caught:
        esolangs.generate("Befunge", "0010" * (1 << 12))
    assert "fixed 80x25 grid" in caught.value.__notes__[0]


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
    with pytest.raises(esolangs.ProgramError, match="expected '0' or '1'"):
        esolangs.read_answer("brainfuck", "answer: unknown\n")


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


def test_bound_template_language_runs_each_input_row():
    language = esolangs.Language("RAM0")
    template = language.generate("0110", width=1)
    assert _evaluate(language.name, template, timeout=None, inputs=2) == "0110"
    for row, answer in enumerate("0110"):
        bits = tuple(map(int, format(row, "02b")))
        program = language.instantiate(template, bits, width=1, truth_table="0110")
        assert language.read_answer(language.run(program, max_steps=1000)) == answer


def test_bound_raster_language_loads_and_evaluates_png(tmp_path):
    language = esolangs.Language("Piet")
    program = language.generate("0110")
    assert isinstance(program, esolangs.Raster)
    path = tmp_path / "program.png"
    path.write_bytes(program.to_png())
    assert _evaluate(language.name, path, inputs=2) == "0110"


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


def test_bound_execution_passes_the_seed():
    language = esolangs.Language("LaserFuck")
    assert [language.run("o+++.\n", seed=0) for _ in range(6)] == ["3"] * 6
