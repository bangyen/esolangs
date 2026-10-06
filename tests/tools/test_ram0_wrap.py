"""RAM0's unary NAND circuit fits one column without changing wider layouts."""

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.tools.ram0 import ram0
from esolangs.tools.wrap import wrap_space_delimited
from tests.witness_tables import witnesses


@pytest.mark.parametrize("n", [1, 2, pytest.param(3, marks=pytest.mark.medium)])
def test_one_column_circuits_execute_every_small_table(n: int) -> None:
    for table in witnesses(n):
        template = esolangs.generate("RAM0", table, 1)
        assert max(map(len, template.splitlines())) == 1
        assert _evaluate("RAM0", template, inputs=n) == table
        for width in (2, 5, 80):
            assert ram0(table, width) == wrap_space_delimited(ram0(table), width)


@pytest.mark.parametrize("table", ["0110", "01101001", "01101001" * 4])
@pytest.mark.parametrize("width", [1, 2, 5])
def test_saved_templates_preserve_exact_provenance(table: str, width: int) -> None:
    template = str(esolangs.generate("RAM0", table, width))
    bits = [0] * (len(table).bit_length() - 1)
    source = esolangs.instantiate("RAM0", template, bits, truth_table=table)
    assert esolangs.read_answer("RAM0", esolangs.run("RAM0", source)) == table[0]
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
    assert sum(len(ram0(format(value, "08b"), 1)) for value in range(256)) == 309606
