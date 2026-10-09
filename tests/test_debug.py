"""Tests for the breakpoint/watch debugger over the VM."""

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.exceptions import UnknownLanguageError
from tests.samples import SAMPLES


class TestBreakpoints:
    def test_break_at_stops_before_target(self) -> None:
        dbg = debugger_api.make_debugger(
            "brainfuck",
            "+++>+++<-.",
        )
        dbg.break_at(3)
        dbg.run()
        assert dbg.ip == 3
        assert dbg.memory == [3]
        assert not dbg.halted

    def test_break_at_zero_fires_immediately(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "+")
        dbg.break_at(0)
        dbg.run()
        assert dbg.ip == 0
        assert dbg.memory == [0]  # the initial cell, not yet incremented

    def test_break_on_cell(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "+++++>++")
        dbg.break_on_cell(0, 5)
        dbg.run()
        assert dbg.memory == [5]  # stops before the '>' moves the pointer

    def test_break_on_cell_beyond_tape_does_not_fire(self) -> None:
        # the watch index never exists, so the run completes
        dbg = debugger_api.make_debugger("brainfuck", "+")
        dbg.break_on_cell(9, 1)
        dbg.run()
        assert dbg.halted

    def test_break_on_stack_top(self) -> None:
        dbg = debugger_api.make_debugger("Eval", "0^")
        dbg.break_on_stack(0, 0)
        dbg.run()
        assert dbg.ip == (1, 1)  # one frame deep, its cursor past the 0
        assert dbg.stack == [0]

    def test_break_on_output(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "+++.")
        dbg.break_on_output("\x03")
        dbg.run()
        assert dbg.output == "\x03"

    def test_break_when_generic(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "++")
        dbg.break_when(lambda vm: vm.memory[0] == 1)
        dbg.run()
        assert dbg.memory == [1]


class TestWatches:
    def test_watch_cell_records_each_step(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "++>+++")
        history = dbg.watch_cell(0)
        for _ in range(3):
            dbg.step()
        assert history == [1, 2, 2]  # None once the pointer moves past

    def test_watch_cell_returns_same_list(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "+")
        first = dbg.watch_cell(0)
        assert dbg.watch_cell(0) is first
        dbg.step()
        assert first == [1]

    def test_watch_stack_returns_same_list(self) -> None:
        dbg = debugger_api.make_debugger("Eval", "0^")
        first = dbg.watch_stack(0)
        assert dbg.watch_stack(0) is first
        dbg.step()
        assert first == [0]

    def test_watch_stack_top(self) -> None:
        dbg = debugger_api.make_debugger("Eval", "0^")
        history = dbg.watch_stack(0)
        dbg.step()
        dbg.step()
        assert history == [0, 0]

    def test_watch_cell_never_grown_records_none(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "+")
        history = dbg.watch_cell(3)
        dbg.step()
        assert history == [None]


class TestEdges:
    """The bounds and the slot arithmetic, pinned where they turn over."""

    def test_no_input_means_no_input(self) -> None:
        """``stdin`` defaults to nothing, not to something."""
        dbg = debugger_api.make_debugger("brainfuck", ",")
        with pytest.raises(EOFError):
            dbg.step()

    def test_watching_the_cell_just_past_the_tape_is_absent(self) -> None:
        # One past the end, where a widened bound indexes out of range
        # instead of reporting the cell does not exist yet.
        dbg = debugger_api.make_debugger("brainfuck", "+")
        history = dbg.watch_cell(1)
        dbg.step()
        assert history == [None]

    def test_breaking_on_the_cell_just_past_the_tape_never_fires(self) -> None:
        dbg = debugger_api.make_debugger("brainfuck", "+")
        dbg.break_on_cell(1, 0)
        dbg.run()
        assert dbg.halted

    def test_watching_a_slot_below_the_top(self) -> None:
        """Slot 1 is the second value down, not the bottom of the stack."""
        dbg = debugger_api.make_debugger("BFStack", ">+>++>+++")
        history = dbg.watch_stack(1)
        dbg.run()
        assert dbg.stack == [1, 2, 3]
        assert history[-1] == 2

    def test_breaking_on_a_slot_below_the_top(self) -> None:
        dbg = debugger_api.make_debugger("BFStack", ">+>++>+++")
        dbg.break_on_stack(1, 2)
        dbg.run()
        assert not dbg.halted
        assert dbg.stack[-2] == 2

    def test_watching_the_slot_just_past_the_stack_is_absent(self) -> None:
        dbg = debugger_api.make_debugger("BFStack", ">+")
        history = dbg.watch_stack(1)
        dbg.step()
        dbg.step()
        assert history == [None, None]


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


class TestARunFinishesTheDump:
    """Six languages finished a *run* holding an empty output."""

    @staticmethod
    def _dumping() -> list[str]:
        """The languages whose answer arrives after the halt, from the data."""
        return [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["dumps_on_the_post_halt_step"]
        ]

    def test_a_breakpoint_can_fire_on_the_dump_step_itself(self) -> None:
        """``run`` reports the breakpoint, not ``"halted"``, when it does."""
        program, stdin = SAMPLES["Minsky Swap"]
        plain = debugger_api.make_debugger("Minsky Swap", program, stdin=stdin)
        assert plain.run(timeout=10) == "halted"
        assert plain.output

        stopped = debugger_api.make_debugger("Minsky Swap", program, stdin=stdin)
        stopped.break_on_output(plain.output)
        assert stopped.run(timeout=10) == "breakpoint"
        assert stopped.output == plain.output

    def test_the_dumping_sets_are_distinct(self) -> None:
        """Named from the registry, and not the *dump answer* set."""
        assert len(self._dumping()) == 9
        mode = {
            n
            for n in esolangs.list_languages()
            if esolangs.describe(n)["answer_mode"] == "dump"
        }
        assert len(mode) == 7
        assert mode != set(self._dumping())

    def test_run_leaves_the_output_in_place(self) -> None:
        """Every dumping language, since the bug was invisible on the rest."""
        empty = []
        for name in self._dumping():
            program = esolangs.generate(name, "0110")
            if esolangs.describe(name)["parameterized"]:
                program, stdin = esolangs.instantiate(name, program, [0, 0]), ""
            else:
                stdin = esolangs.encode_inputs(name, [0, 0], truth_table="0110")
            debugger = debugger_api.make_debugger(name, program, stdin=stdin)
            assert debugger.run(timeout=30) == "halted"
            if not debugger.output:
                empty.append(name)
        assert not empty

    def test_it_agrees_with_run(self) -> None:
        """The comparison that makes it a bug rather than a convention."""
        for name in self._dumping():
            program = esolangs.generate(name, "0110")
            if esolangs.describe(name)["parameterized"]:
                program, stdin = esolangs.instantiate(name, program, [0, 0]), ""
            else:
                stdin = esolangs.encode_inputs(name, [0, 0], truth_table="0110")
            debugger = debugger_api.make_debugger(name, program, stdin=stdin)
            debugger.run(timeout=30)
            assert debugger.output == esolangs.run(
                name, program, stdin=stdin, timeout=30
            ), name

    def test_an_ordinary_language_takes_no_extra_step(self) -> None:
        """The step is a no-op elsewhere, but it would land in every watch."""
        debugger = debugger_api.make_debugger("brainfuck", "+++.", stdin="")
        history = debugger.watch_cell(0)
        debugger.run(timeout=10)
        assert len(history) == 4  # three increments and the print, no more


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
