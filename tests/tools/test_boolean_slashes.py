"""Constant roots and template recognition for ///."""

import pytest

import esolangs
from esolangs._evaluate import _evaluate
from esolangs.debugger import make_vm
from esolangs.exceptions import TemplateError
from esolangs.tools.slashes import _is_unfilled_template
from scripts.benchmark import WrittenState


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_root_deletes_inputs_without_selecting_a_table(inputs, bit):
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
def test_constant_recognizer_does_not_reserve_other_literal_dollars(suffix):
    assert not _is_unfilled_template("/a///b//" + suffix)


def test_partly_filled_constant_still_requires_its_remaining_input():
    assert _is_unfilled_template("/a///b//a$b1")
    assert esolangs.run("///", "$0") == "$0"
