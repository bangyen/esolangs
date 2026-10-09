"""RAM0 through the shared API, CLI and machinery."""

import esolangs
from esolangs._evaluate import _evaluate


def test_bound_template_language_runs_each_input_row():
    language = esolangs.Language("RAM0")
    template = language.generate("0110", width=1)
    assert _evaluate(language.name, template, timeout=None, inputs=2) == "0110"
    for row, answer in enumerate("0110"):
        bits = tuple(map(int, format(row, "02b")))
        program = language.instantiate(template, bits, width=1, truth_table="0110")
        assert language.read_answer(language.run(program, max_steps=1000)) == answer
