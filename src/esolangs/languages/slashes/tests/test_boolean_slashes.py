"""Constant roots and template recognition for ///."""

import pytest

import esolangs
from esolangs.debugger import make_vm
from esolangs.exceptions import TemplateError
from esolangs.generation.helpers import essential_inputs
from esolangs.generation.wrap import wrap_program
from esolangs.languages.slashes.generator import (
    _DECODE,
    _IGNORE,
    _SWEEP,
    _UNARY,
    _is_unfilled_template,
)
from esolangs.runtime._evaluate import _evaluate
from scripts.benchmark import WrittenState
from tests.support.witness_tables import witnesses


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_source_length_is_the_documented_formula(n: int) -> None:
    """Worst case 20 * 2**m + n + 35, plus k + 10 for k ignored inputs.

    Reached when the first 2**m - 1 entries are all ``0``: one entry per
    sweep.  A ``0`` before a ``1`` shares a sweep and trims 18 characters.
    """
    for table in witnesses(n):
        m = len(essential_inputs(table, n))
        k = n - m
        size = 20 * 2**m + n + 35 + (k + 10 if k else 0)
        if len(set(table)) == 1:
            size = n + 9
        assert len(esolangs.generate("///", table)) <= size, table
    table = "0" * (2**n - 1) + "1"
    assert len(esolangs.generate("///", table)) == 20 * 2**n + n + 35


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


def test_all_slots_ignored_is_still_a_template() -> None:
    # read == 0: the one slot is an ignored X and the table has one entry.
    program = _IGNORE + _UNARY + _DECODE + "X$>qA"
    assert _is_unfilled_template(program)


def test_filled_slots_are_not_a_template() -> None:
    # No $ in the slots: a and b are filled values, not template slots,
    # even when the rest of the string is canonical.
    program = _UNARY + _SWEEP * 4 + _DECODE + "ab>qAqAqAqA"
    assert not _is_unfilled_template(program)


def test_more_ignored_slots_than_slots_is_a_program_not_a_template() -> None:
    # Two X in a three-character slot list once shifted by -1 and raised.
    program = _UNARY + _DECODE + "$XX>qAqB"
    assert not _is_unfilled_template(program)
    assert isinstance(esolangs.run("///", program), str)


def test_ignored_input_template_is_recognized_only_while_canonical() -> None:
    template = esolangs.generate("///", "0011")  # slots "$X$": one ignored
    assert template.endswith("$X$>qAqB")
    assert _is_unfilled_template(template)
    body = template.removesuffix("$X$>qAqB")
    assert not _is_unfilled_template(body + "$X1>qAqB")  # a filled slot
    assert not _is_unfilled_template(body + "$X$>qAXB")  # a foreign cell


def test_partly_filled_constant_still_requires_its_remaining_input() -> None:
    assert _is_unfilled_template("/a///b//a$b1")
    assert esolangs.run("///", "$0") == "$0"


def test_unwrappable_source_is_untouched() -> None:
    assert wrap_program("iiiioddo", "slashes", 4) == "iiiioddo"


@pytest.mark.parametrize(
    "table", ["00", "11", "0110", "00001111", "01010101", "0001000100010001"]
)
def test_balanced_program_folds_behind_the_newline_rule(table: str) -> None:
    """Constant, ignored-input and full tables all run once folded."""
    from esolangs.generation.wrap import balance_score

    n = len(table).bit_length() - 1
    plain = str(esolangs.generate("///", table))
    balanced = str(esolangs.generate("///", table, balance=True))
    assert balance_score(balanced) <= balance_score(plain)
    assert _evaluate("///", balanced, inputs=n) == table
    assert _evaluate("///", balanced, inputs=n) != table[:-1] + str(1 - int(table[-1]))


def test_balanced_side_is_square_at_n8() -> None:
    """Seed 8: 4011 chars on one line fold to 46 x 92 behind the rule."""
    import random

    from esolangs.generation.wrap import balance_score

    table = format(random.Random(8).getrandbits(256), "0256b")
    balanced = str(esolangs.generate("///", table, balance=True))
    assert balance_score(balanced)[0] == 92
    assert balanced.startswith("/\n//")
