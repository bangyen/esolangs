"""Constant roots and template recognition for ///."""

import random

import pytest

import esolangs
from esolangs.exceptions import TemplateError
from esolangs.generation.wrap import balance_score, wrap_program
from esolangs.languages.slashes import generator as boolean
from esolangs.languages.slashes.tests.template_shape import _is_unfilled_template
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import _capture_workspace, make_vm
from scripts.benchmark import WrittenState
from tests.support.analysis_support import assert_analysis_complement
from tests.support.evaluation import _evaluate
from tests.support.witness_tables import witnesses


@pytest.mark.parametrize("n", [1, 2, 3, 4])
def test_source_length_is_the_documented_formula(n: int) -> None:
    """Alternating run boundaries maximize the compressed sweep count."""
    from scripts.docs.resource_evidence import resource_bounds

    scaling = resource_bounds("///")["scaling"].formula

    if n == 1:
        _check_run_macros()
    for table in witnesses(n):
        assert len(esolangs.generate("///", table).source) <= scaling(n, ""), table
    table = (
        "10" if n == 1 else "10111011" if n == 3 else "10" * (2 ** (n - 1) - 1) + "11"
    )
    assert len(esolangs.generate("///", table).source) == scaling(n, "")


@pytest.mark.medium
@pytest.mark.parametrize("inputs", [1, 3, 8])
@pytest.mark.parametrize("bit", ["0", "1"])
def test_constant_root_parses_inputs_without_selecting_a_table(inputs, bit) -> None:
    if inputs == 1 and bit == "0":
        _check_constants()
    table = bit * (1 << inputs)
    template = esolangs.generate("///", table)
    assert len(template.source) == inputs + 4
    assert template.source.count("$") == inputs
    assert _evaluate("///", template, inputs=inputs) == table
    assert _is_unfilled_template(template.source)
    with pytest.raises(TemplateError, match="fill the template"):
        esolangs.run("///", template)
    for row in (0, (1 << inputs) - 1):
        bits = [int(c) for c in format(row, f"0{inputs}b")]
        program = esolangs.instantiate("///", template, bits)
        assert not _is_unfilled_template(program.source)
        vm = make_vm("///", program)
        state = WrittenState(_capture_workspace(vm))
        commands = 0
        while not vm.halted and commands < inputs + 5:
            vm.step()
            state.sample(_capture_workspace(vm))
            commands += 1
        assert vm.halted
        assert vm.output == bit
        assert commands == 3
        assert state.bits <= 16 * inputs + 32


@pytest.mark.parametrize("suffix", ["", "0", "$", "$2", "$x0", "ab0"])
def test_constant_recognizer_does_not_reserve_other_literal_dollars(suffix) -> None:
    assert not _is_unfilled_template("/a///b//" + suffix)


def test_former_all_ignored_layout_is_not_a_template() -> None:
    program = boolean._IGNORE + boolean._UNARY + boolean._DECODE + "X$>qA"
    assert not hasattr(boolean, "_CONSTANT")
    assert not _is_unfilled_template(program)


def test_filled_slots_are_not_a_template() -> None:
    # No $ in the slots: a and b are filled values, not template slots,
    # even when the rest of the string is canonical.
    program = boolean._UNARY + boolean._SWEEP * 4 + boolean._DECODE + "ab>qAqAqAqA"
    assert not _is_unfilled_template(program)


def test_more_ignored_slots_than_slots_is_a_program_not_a_template() -> None:
    # Two X in a three-character slot list once shifted by -1 and raised.
    program = boolean._UNARY + boolean._DECODE + "$XX>qAqB"
    assert not _is_unfilled_template(program)
    assert isinstance(esolangs.run("///", program).output, str)


def test_ignored_input_template_is_recognized_only_while_canonical() -> None:
    assert_analysis_complement("///", "input_weights")
    template = esolangs.generate("///", "0011")  # slots "$X$": one ignored
    assert template.source.endswith("$X$>qAqB")
    assert _is_unfilled_template(template.source)
    body = template.source.removesuffix("$X$>qAqB")
    assert not _is_unfilled_template(body + "$X1>qAqB")  # a filled slot
    assert not _is_unfilled_template(body + "$X$>qAXB")  # a foreign cell


def test_partly_filled_constant_still_requires_its_remaining_input() -> None:
    assert _is_unfilled_template("/a$b//1")
    assert esolangs.run("///", "$0").output == "$0"


def test_unwrappable_source_is_untouched() -> None:
    assert wrap_program("iiiioddo", "slashes", 4) == "iiiioddo"


@pytest.mark.parametrize(
    "table", ["00", "11", "0110", "00001111", "01010101", "0001000100010001"]
)
def test_balanced_program_folds_behind_the_newline_rule(table: str) -> None:
    """Constant, ignored-input and full tables all run once folded."""
    n = len(table).bit_length() - 1
    plain = esolangs.generate("///", table)
    balanced = esolangs.generate("///", table, balance=True)
    assert balance_score(balanced.source) <= balance_score(plain.source)
    assert _evaluate("///", balanced, inputs=n) == table
    assert _evaluate("///", balanced, inputs=n) != table[:-1] + str(1 - int(table[-1]))


def test_balanced_side_is_square_at_n8() -> None:
    """Seed 8 folds to 18 x 38 behind the newline rule."""
    table = format(random.Random(8).getrandbits(256), "0256b")
    balanced = esolangs.generate("///", table, balance=True)
    assert balance_score(balanced.source)[0] == 38
    assert balanced.source.startswith("/\n//")


def _check_run_macros() -> None:
    from esolangs.languages.slashes.generator import _SWEEP_DEF
    from esolangs.languages.slashes.interpreter import _Machine
    from scripts.docs.resource_evidence import resource_bounds

    workspace = resource_bounds("///")["workspace"].formula

    io = ScriptedIO("Q")
    machine = _Machine(_SWEEP_DEF + "SS", io)
    for _ in range(4):
        machine.step()
    assert machine.state == (boolean._SWEEP * 2, None)
    for table in ("1011", "10111011", "00010100", "0101101000011010"):
        n = len(table).bit_length() - 1
        for balanced in (False, True):
            template = esolangs.generate("///", table, balance=balanced)
            assert balanced or _is_unfilled_template(template.source)
            for row in range(1 << n):
                program = esolangs.instantiate(
                    "///", template, [int(c) for c in f"{row:0{n}b}"]
                )
                io = ScriptedIO("Q")
                machine = _Machine(program.source, io)
                written = WrittenState(machine.workspace_snapshot())
                while not machine.halted:
                    machine.step()
                    written.sample(machine.workspace_snapshot())
                assert io.getvalue() == table[row]
                assert io.reads == 0
                assert io.input_char() == ord("Q")
                if not balanced:
                    assert written.bits <= workspace(n, template.source)
                    if row == (1 << n) - 1:
                        assert written.bits == workspace(n, template.source)


def _check_constants() -> None:
    from esolangs.languages.slashes.interpreter import _Machine

    for n in range(1, 13):
        for bit in "01":
            for options in ({}, {"width": 1}, {"balance": True}):
                template = esolangs.generate("///", bit * (1 << n), **options)
                for bits in ([0] * n, [1] * n):
                    program = esolangs.instantiate("///", template, bits)
                    io = ScriptedIO("7")
                    machine = _Machine(program.source, io)
                    pattern = "".join("ab"[b] for b in bits)
                    parsed = False
                    for _ in range(20):
                        if machine.halted:
                            break
                        machine.step()
                        if machine.state[1] == (pattern, ""):
                            parsed = True
                        if io.getvalue():
                            assert parsed
                    assert machine.halted
                    assert parsed
                    assert io.getvalue() == bit
                    assert io.reads == 0
                    assert io.input_char() == ord("7")


def test_ignored_markers_must_prefix_their_own_slot() -> None:
    for slots in ("XX$$", "$XX$", "X$$X", "$$XX"):
        program = boolean._IGNORE + boolean._UNARY + boolean._DECODE + slots + ">qA"
        assert not _is_unfilled_template(program)
