"""Tests for the step-and-inspect VM wrapper."""

import pytest

import esolangs
from esolangs.exceptions import UnknownLanguageError
from esolangs.vm import VM


def _run_all(vm: VM) -> str:
    while not vm.halted:
        vm.step()
    return vm.output


class TestProtocol:
    def test_implements_vm_protocol(self) -> None:
        assert isinstance(esolangs.make_vm("brainfuck", "+"), VM)


class TestBrainfuck:
    def test_tape_and_cursor_evolve(self) -> None:
        vm = esolangs.make_vm("brainfuck", "++.")
        assert (vm.ip, vm.memory, vm.output) == (0, [0], "")
        vm.step()
        assert (vm.ip, vm.memory) == (1, [1])
        vm.step()
        assert (vm.ip, vm.memory) == (2, [2])
        vm.step()
        assert vm.output == "\x02"
        assert vm.halted

    def test_run_matches_execute(self) -> None:
        assert _run_all(esolangs.make_vm("brainfuck", "+++[>+++<-]>.")) == esolangs.run(
            "brainfuck", "+++[>+++<-]>."
        )


class TestSbleq:
    def test_oisc_cells_and_ip(self) -> None:
        vm = esolangs.make_vm("S*bleq", "-3 11 3")
        assert (vm.ip, vm.halted) == (0, False)
        vm.step()
        assert (vm.ip, vm.halted, vm.output) == (3, True, "\x00")


class TestDimensional:
    def test_byte_value_exposed(self) -> None:
        vm = esolangs.make_vm("Dimensional", "++.")
        assert vm.memory == [0]
        vm.step()
        assert vm.memory == [1]
        vm.step()
        assert vm.memory == [2]
        vm.step()
        assert vm.output == "\x02"


class TestGrapheme:
    def test_stack_exposed(self) -> None:
        vm = esolangs.make_vm("Grapheme", "FAFY")
        assert vm.stack == []
        vm.step()  # F starts int mode
        vm.step()  # A accumulates
        vm.step()  # F ends int mode, pushes 10
        assert vm.stack == [10]
        vm.step()  # Y prints
        assert vm.output == "10"
        assert vm.halted

    def test_rejects_non_uppercase(self) -> None:
        with pytest.raises(ValueError, match="uppercase"):
            esolangs.make_vm("Grapheme", "a")


class TestQoibl:
    def test_expression_cursor(self) -> None:
        vm = esolangs.make_vm("Qoibl", "et")
        assert vm.ip == 0
        assert not vm.halted
        with pytest.raises(EOFError):
            vm.step()


class TestEval:
    def test_active_stack_exposed(self) -> None:
        vm = esolangs.make_vm("Eval", "0^")
        vm.step()
        assert vm.stack == [0]
        vm.step()
        assert vm.stack == [0, 0]


class TestModulous:
    def test_token_cursor_and_stack(self) -> None:
        vm = esolangs.make_vm("Modulous", "[PSH INT 5][PRT INT]")
        vm.step()
        assert vm.stack == [5]
        vm.step()
        assert vm.output == "5"
        assert vm.halted


class TestTemporaryStack:
    def test_word_pointer_and_stack(self) -> None:
        vm = esolangs.make_vm("The Temporary Stack", "v5 +")
        vm.step()
        assert vm.stack == [5]
        vm.step()
        assert vm.stack == [5, 5]


class TestLaserFuck:
    def test_ip_is_position_and_heading(self) -> None:
        # heading is fixed to 0 (up), so the laser at (2,4) moves up
        vm = esolangs.make_vm("LaserFuck", "\u00ff   x\n    +\n    o")
        assert vm.ip == (2, 4, 0)  # the laser's start position and heading
        vm.step()
        assert vm.ip == (1, 4, 0)  # moved up onto the '+'
        assert vm.memory == [1]
        vm.step()
        assert vm.ip == (0, 4, 0)  # moved up onto the 'x', died
        assert vm.halted
        assert vm.output == "\x01"

    def test_dump_output_matches_interpreter(self) -> None:
        from esolangs.interpreters.grid_based.laserfuck import run as lf_run
        from esolangs.interpreters.io import ScriptedIO

        program = "\u00ff   x\n    +\n    o"
        io_obj = ScriptedIO()
        lf_run(program.splitlines(), io_obj, heading=0)
        vm = esolangs.make_vm("LaserFuck", program)
        assert _run_all(vm) == io_obj.getvalue()


class TestFactory:
    def test_unknown_language_raises(self) -> None:
        with pytest.raises(UnknownLanguageError):
            esolangs.make_vm("NoSuchLanguage", "+")
        with pytest.raises(UnknownLanguageError):
            esolangs.make_vm("Forþ", "1 1 + .")  # no step-capable interpreter


@pytest.mark.parametrize(
    ("language", "program"),
    [
        ("brainfuck", "+++[>+++<-]>."),
        ("S*bleq", "-3 11 3"),
        ("Dimensional", "+.+.+."),
        ("Grapheme", "FAFY"),
        ("Qoibl", "we y we yyeeee we\ntt qe y qe tt"),
        ("Eval", "0+."),
        ("Modulous", "[PSH INT 5][DUP][PRT INT]"),
        ("The Temporary Stack", "v5 *AB"),
    ],
)
def test_vm_output_matches_run(language: str, program: str) -> None:
    """Stepping a VM to completion matches running the interpreter directly."""
    try:
        expected = esolangs.run(language, program)
    except EOFError:
        pytest.skip(f"{language} needs input")
    vm = esolangs.make_vm(language, program)
    assert _run_all(vm) == expected
