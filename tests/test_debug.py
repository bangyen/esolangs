"""Tests for the breakpoint/watch debugger over the VM."""

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.exceptions import UnknownLanguageError


class TestRun:
    def test_run_to_completion_matches_interpreter(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "+++[>+++<-]>.")
        dbg.run()
        assert dbg.halted
        assert dbg.output == esolangs.run("brainfuck", "+++[>+++<-]>.")

    def test_max_steps_bounds_runaway(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "+[]")
        dbg.run(max_steps=10)
        assert not dbg.halted

    def test_step_guards_on_halt(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "+")
        dbg.run()
        dbg.step()  # must not raise
        assert dbg.halted


class TestFactory:
    def test_unknown_language_raises(self) -> None:
        with pytest.raises(UnknownLanguageError):
            debugger_api.make_debugger("NoSuchLanguage", "+")


#: Two of the nine dump-on-post-halt languages, one reader and one template:
#: the dump step is the debugger's shared code, and test_vm_protocol already
#: checks every language's flag against its behaviour.
_DUMPERS = ("LaserFuck", "RAM0")


def _runnable(name: str, table: str = "0110") -> tuple[str, str]:
    """Return a filled program and the stdin to drive it with."""
    program = esolangs.generate(name, table)
    if esolangs.describe(name)["parameterized"]:
        return esolangs.instantiate(name, program, [0, 0]), ""
    return program, esolangs.encode_inputs(name, [0, 0])


class TestABreakpointAtTheHaltIsReported:
    """``run`` reported ``"halted"`` over a watch that had fired."""

    def test_an_output_watch_on_the_last_step_fires(self) -> None:
        """The case it was reported for, on the flagship language."""
        dbg = debugger_api.make_debugger(
            "brainfuck", esolangs.generate("brainfuck", "0110"), stdin="10"
        )
        dbg.break_on_output("1")
        assert dbg.run(max_steps=100_000) == "breakpoint"
        assert dbg.run(max_steps=100_000) == "halted"
        assert dbg.halted

    @pytest.mark.parametrize("name", _DUMPERS)
    def test_the_answer_is_never_stranded_by_that_stop(self, name: str) -> None:
        """A stop before the dump must not cost the caller the answer."""
        assert esolangs.describe(name)["dumps_on_the_post_halt_step"]
        program, stdin = _runnable(name)
        dbg = debugger_api.make_debugger(name, program, stdin=stdin)
        dbg.break_when(lambda vm: vm.halted and vm.output == "")
        assert dbg.run(max_steps=300_000) == "breakpoint"
        assert dbg.output == ""
        assert dbg.run(max_steps=300_000) == "halted"
        assert dbg.output == esolangs.run(name, program, stdin=stdin, timeout=30)

    @pytest.mark.parametrize("name", _DUMPERS)
    def test_the_dump_step_is_taken_once_not_once_per_run(self, name: str) -> None:
        """Three idle runs grew a watch history by three."""
        program, stdin = _runnable(name)
        dbg = debugger_api.make_debugger(name, program, stdin=stdin)
        history = dbg.watch_cell(0)
        dbg.run(max_steps=300_000)
        after_one = len(history)
        for _ in range(4):
            dbg.run(max_steps=300_000)
        assert len(history) == after_one


def _step_to_halt(dbg: debugger_api.Debugger, budget: int = 200_000) -> None:
    """Drive ``dbg`` with ``step()`` alone until it halts."""
    for _ in range(budget):
        if dbg.halted:
            return
        dbg.step()


class TestSteppingWarnsAboutStdinToo:
    """The warning fired under ``run`` and not under ``step``."""

    @staticmethod
    def _eof_is_a_value() -> list[str]:
        """The languages that carry on, which is the set that must warn."""
        return [
            pytest.param(
                name,
                # Malbolge's program is the full 59049-cell store, so stepping
                # it to its halt one instruction at a time is a medium run.
                marks=pytest.mark.medium if name == "Malbolge" else (),
            )
            for name in esolangs.list_languages()
            if esolangs.describe(name)["boolean_generator"]
            and esolangs.describe(name)["eof_is_a_value"]
            and not esolangs.describe(name)["parameterized"]
            and name != "Alight"
        ]

    def test_alight_refuses_instead_of_warning(self) -> None:
        """The documented exception, pinned so it stays a *loud* one."""
        program = esolangs.generate("Alight", "0110")
        full = esolangs.encode_inputs("Alight", [1, 0])
        short = "\n".join(full.split("\n")[:-2]) + "\n"
        dbg = debugger_api.make_debugger("Alight", program, stdin=short)
        with pytest.raises(esolangs.HaltError, match="eof"):
            _step_to_halt(dbg)
