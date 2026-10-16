"""Constant roots and template recognition for ///."""

import pytest

import esolangs
from esolangs.debugger import make_vm
from esolangs.exceptions import TemplateError
from esolangs.generation.helpers import essential_inputs
from esolangs.generation.wrap import wrap_program
from esolangs.languages.slashes.generator import _is_unfilled_template
from esolangs.runtime._evaluate import _evaluate
from scripts.benchmark import WrittenState
from tests.support.witness_tables import witnesses


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_source_length_is_the_documented_formula(n: int) -> None:
    """limitations.md: 20 * 2**m + n + 53, plus k + 10 for k ignored inputs."""
    for table in witnesses(n):
        m = len(essential_inputs(table, n))
        k = n - m
        size = 20 * 2**m + n + 53 + (k + 10 if k else 0)
        if len(set(table)) == 1:
            size = n + 9
        assert len(esolangs.generate("///", table)) == size, table


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_root_deletes_inputs_without_selecting_a_table(inputs, bit) -> None:
    table = bit * (1 << inputs)
    template = esolangs.generate("///", table)
    assert len(template) == inputs + 9
    assert template.count("$") == inputs
    assert _evaluate("///", template, inputs=inputs) == table
    assert _is_unfilled_template(str(template))
    with pytest.raises(TemplateError, match="unfilled"):
        esolangs.run("///", str(template))
    for row in (0, (1 << inputs) - 1):
        bits = [int(c) for c in format(row, f"0{inputs}b")]
        program = esolangs.instantiate("///", template, bits)
        assert not _is_unfilled_template(str(program))
        vm = make_vm("///", program)
        state = WrittenState(vm.snapshot())
        commands = 0
        while not vm.halted and commands < inputs + 5:
            vm.step()
            state.sample(vm.snapshot())
            commands += 1
        assert vm.halted
        assert vm.output == bit
        assert commands == inputs + 5
        assert state.bits <= 8 * len(program) + 56


@pytest.mark.parametrize("suffix", ["", "0", "$", "$2", "$x0", "ab0"])
def test_constant_recognizer_does_not_reserve_other_literal_dollars(suffix) -> None:
    assert not _is_unfilled_template("/a///b//" + suffix)


def test_partly_filled_constant_still_requires_its_remaining_input() -> None:
    assert _is_unfilled_template("/a///b//a$b1")
    assert esolangs.run("///", "$0") == "$0"


def test_unwrappable_source_is_untouched() -> None:
    assert wrap_program("iiiioddo", "slashes", 4) == "iiiioddo"
