"""Algebraic Programming Language through the shared API, CLI and machinery."""

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.vm import make_vm, run_until_halt_or_ancestor


class TestTheVmPathRefusesLikeRunDoes:
    """``run`` translated an interpreter's exceptions and the VM did not."""

    JUNK = ("]", "}", ")", "ZZZ", "[", "\x00")

    @pytest.mark.parametrize("entry", ["make_vm", "make_debugger"])
    def test_a_malformed_program_is_a_program_error(self, entry: str) -> None:
        """The one-character case, on the language it was reported for."""
        with pytest.raises(esolangs.ProgramError, match="unmatched"):
            getattr(debugger_api, entry)("brainfuck", "]")

    def test_no_language_leaks_anything_else(self) -> None:
        """Every language against six kinds of junk, both entry points."""
        escapes = []
        for name in esolangs.list_languages():
            for junk in self.JUNK:
                for entry in ("make_vm", "make_debugger"):
                    try:
                        getattr(debugger_api, entry)(name, junk)
                    except esolangs.EsolangError:
                        pass
                    except Exception as exc:
                        escapes.append((name, entry, junk, type(exc).__name__))
        assert not escapes, escapes[:5]

    def test_the_two_paths_agree_on_the_class(self) -> None:
        """Not merely "both raise" -- both raise the *same* thing."""
        for entry in (debugger_api.make_vm, debugger_api.make_debugger):
            with pytest.raises(esolangs.ProgramError) as stepped:
                entry("brainfuck", "]")
            with pytest.raises(esolangs.ProgramError) as ran:
                esolangs.run("brainfuck", "]")
            assert str(stepped.value) == str(ran.value)

    def test_a_recursion_limit_is_an_interpreter_limit(self) -> None:
        """Ninety open parens raised a bare ``RecursionError`` from ``step``."""
        vm = debugger_api.make_vm("Algebraic Programming Language", "(" * 90)
        with pytest.raises(esolangs.InterpreterLimitError):
            vm.step()


def test_the_ancestor_detector_takes_a_vm() -> None:
    """APL's truth machine, the shape the frame stack exists for."""
    truth = "x? = x & x?\nn?"
    halts = make_vm("Algebraic Programming Language", truth, stdin="0\n")
    assert run_until_halt_or_ancestor(halts) is True
    hangs = make_vm("Algebraic Programming Language", truth, stdin="1\n")
    assert run_until_halt_or_ancestor(hangs) is False
