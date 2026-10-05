"""Bound-language workflows retain the package's source and execution contracts."""

from concurrent.futures import ThreadPoolExecutor

import pytest

import esolangs
from esolangs import _check_program
from esolangs._evaluate import _evaluate
from tests.stdin_check import _check_stdin


def test_bound_language_runs_a_boolean_workflow():
    language = esolangs.Language(" BRAINFUCK ")
    assert language.name == "brainfuck"
    assert language.describe()["name"] == language.name
    program = language.generate("0110", balance=True)
    stdin = language.encode_inputs([0, 1], "0110")
    _check_stdin(language.name, stdin, "0110")
    assert _check_program(language.name, program, stdin) == program
    assert language.read_answer(language.run(program, stdin)) == "1"
    assert _evaluate(language.name, program, inputs=2) == "0110"


def test_unknown_language_is_refused_at_construction():
    with pytest.raises(esolangs.UnknownLanguageError):
        esolangs.Language("brainfuk")


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
    with pytest.raises(esolangs.ArgumentError, match="finite timeout"):
        language.run(path, isolated=True, timeout=None)


def test_bound_execution_keeps_partial_output_on_step_exhaustion():
    language = esolangs.Language("brainfuck")
    with pytest.raises(esolangs.ExecutionTimeoutError) as caught:
        language.run("+.[]", max_steps=10, timeout=1)
    assert caught.value.partial_output == "\x01"


def test_bound_execution_passes_the_seed():
    language = esolangs.Language("LaserFuck")
    assert [language.run("o+++.\n", seed=0) for _ in range(6)] == ["3"] * 6
