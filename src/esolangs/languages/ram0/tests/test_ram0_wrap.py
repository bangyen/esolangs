"""RAM0's unary NAND circuit fits one column without changing wider layouts."""

import json

import pytest

import esolangs
from esolangs import run
from esolangs.generation.wrap import wrap_space_delimited
from esolangs.languages.ram0.generator import ram0
from tests.support.evaluation import _evaluate
from tests.support.witness_tables import witnesses


@pytest.mark.parametrize("n", [1, 2, pytest.param(3, marks=pytest.mark.medium)])
def test_one_column_circuits_execute_every_small_table(n: int) -> None:
    for table in witnesses(n):
        template = esolangs.generate("RAM0", table, width=1)
        assert max(map(len, template.source.splitlines())) == 1
        assert _evaluate("RAM0", template, inputs=n) == table
        for width in (2, 5, 80):
            assert ram0(table, width) == wrap_space_delimited(ram0(table), width)


@pytest.mark.parametrize("table", ["0110", "01101001", "01101001" * 4])
@pytest.mark.parametrize("width", [1, 2, 5])
def test_saved_templates_preserve_exact_provenance(
    table: str, width: int, monkeypatch
) -> None:
    def unexpected_scan(*_args):
        raise AssertionError("structured layout rediscovered its slots")

    with monkeypatch.context() as patch:
        patch.setattr("esolangs.artifacts.runs", unexpected_scan)
        original = esolangs.generate("RAM0", table, width=width)
        balanced = esolangs.generate("RAM0", table, balance=True)
        document = esolangs.dump_program("RAM0", original)
        template = esolangs.load_program("RAM0", document)
    assert original == template
    assert balanced.spans is not None
    legacy = json.loads(document)
    del legacy["spans"]
    with pytest.raises(esolangs.ProgramError, match="missing fields"):
        esolangs.load_program("RAM0", json.dumps(legacy))
    damaged = json.loads(document)
    damaged["spans"][0][0] += 1
    with pytest.raises(esolangs.ProgramError, match="invalid template span"):
        esolangs.load_program("RAM0", json.dumps(damaged))
    bits = [0] * (len(table).bit_length() - 1)
    source = esolangs.instantiate("RAM0", template, bits, truth_table=table)
    assert esolangs.read_answer("RAM0", run("RAM0", source).output) == table[0]
    with pytest.raises(esolangs.TemplateError):
        esolangs.instantiate(
            "RAM0",
            template,
            bits,
            truth_table=table.translate(str.maketrans("01", "10")),
        )


def test_unary_address_cost_is_bounded_to_small_arities() -> None:
    table = "01101001" * 2
    assert ram0(table, 1) == wrap_space_delimited(ram0(table), 1)


def test_one_column_corpus_size() -> None:
    assert len(ram0("0110", 1)) == 735
    assert sum(len(ram0(format(value, "08b"), 1)) for value in range(256)) == 309490
