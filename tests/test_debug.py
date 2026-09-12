"""Tests for the breakpoint/watch debugger over the VM."""

import warnings

import pytest

import esolangs
from esolangs.exceptions import UnknownLanguageError


class TestBreakpoints:
    def test_break_at_stops_before_target(self) -> None:
        dbg = esolangs.make_debugger(
            "brainfuck",
            "+++>+++<-.",
        )
        dbg.break_at(3)
        dbg.run()
        assert dbg.ip == 3
        assert dbg.memory == [3]
        assert not dbg.halted

    def test_break_at_zero_fires_immediately(self) -> None:
        dbg = esolangs.make_debugger("brainfuck", "+")
        dbg.break_at(0)
        dbg.run()
        assert dbg.ip == 0
        assert dbg.memory == [0]  # the initial cell, not yet incremented

    def test_break_on_cell(self) -> None:
        dbg = esolangs.make_debugger("brainfuck", "+++++>++")
        dbg.break_on_cell(0, 5)
        dbg.run()
        assert dbg.memory == [5]  # stops before the '>' moves the pointer

    def test_break_on_cell_beyond_tape_does_not_fire(self) -> None:
        # the watch index never exists, so the run completes
        dbg = esolangs.make_debugger("brainfuck", "+")
        dbg.break_on_cell(9, 1)
        dbg.run()
        assert dbg.halted

    def test_break_on_stack_top(self) -> None:
        dbg = esolangs.make_debugger("Eval", "0^")
        dbg.break_on_stack(0, 0)
        dbg.run()
        assert dbg.ip == (1, 1)  # one frame deep, its cursor past the 0
        assert dbg.stack == [0]

    def test_break_on_output(self) -> None:
        dbg = esolangs.make_debugger("brainfuck", "+++.")
        dbg.break_on_output("\x03")
        dbg.run()
        assert dbg.output == "\x03"

    def test_break_when_generic(self) -> None:
        dbg = esolangs.make_debugger("brainfuck", "++")
        dbg.break_when(lambda vm: vm.memory[0] == 1)
        dbg.run()
        assert dbg.memory == [1]


class TestWatches:
    def test_watch_cell_records_each_step(self) -> None:
        dbg = esolangs.make_debugger("brainfuck", "++>+++")
        history = dbg.watch_cell(0)
        for _ in range(3):
            dbg.step()
        assert history == [1, 2, 2]  # None once the pointer moves past

    def test_watch_cell_returns_same_list(self) -> None:
        """Watching a cell again hands back the history already being kept."""
        dbg = esolangs.make_debugger("brainfuck", "+")
        first = dbg.watch_cell(0)
        assert dbg.watch_cell(0) is first
        dbg.step()
        assert first == [1]

    def test_watch_stack_returns_same_list(self) -> None:
        """Watching a slot again hands back the history already being kept."""
        dbg = esolangs.make_debugger("Eval", "0^")
        first = dbg.watch_stack(0)
        assert dbg.watch_stack(0) is first
        dbg.step()
        assert first == [0]

    def test_watch_stack_top(self) -> None:
        dbg = esolangs.make_debugger("Eval", "0^")
        history = dbg.watch_stack(0)
        dbg.step()
        dbg.step()
        assert history == [0, 0]

    def test_watch_cell_never_grown_records_none(self) -> None:
        dbg = esolangs.make_debugger("brainfuck", "+")
        history = dbg.watch_cell(3)
        dbg.step()
        assert history == [None]


class TestRun:
    def test_run_to_completion_matches_interpreter(self) -> None:
        dbg = esolangs.make_debugger("brainfuck", "+++[>+++<-]>.")
        dbg.run()
        assert dbg.halted
        assert dbg.output == esolangs.run("brainfuck", "+++[>+++<-]>.")

    def test_max_steps_bounds_runaway(self) -> None:
        dbg = esolangs.make_debugger("brainfuck", "+[]")
        dbg.run(max_steps=10)
        assert not dbg.halted

    def test_step_guards_on_halt(self) -> None:
        dbg = esolangs.make_debugger("brainfuck", "+")
        dbg.run()
        dbg.step()  # must not raise
        assert dbg.halted


class TestFactory:
    def test_unknown_language_raises(self) -> None:
        with pytest.raises(UnknownLanguageError):
            esolangs.make_debugger("NoSuchLanguage", "+")

    def test_registered_language_without_an_adapter_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A registry language missing from ``_VM_ADAPTERS`` also raises.

        Every current registry language has an adapter, so this exercises
        ``make_vm``'s defensive fallback (not just the unregistered-name
        check) by removing one adapter for the duration of the test.
        """
        from esolangs.vm import _VM_ADAPTERS

        monkeypatch.delitem(_VM_ADAPTERS, "brainfuck")
        with pytest.raises(UnknownLanguageError):
            esolangs.make_debugger("brainfuck", "+")


class TestARunFinishesTheDump:
    """Seven languages finished a *run* holding an empty output.

    ``Debugger.step`` learned to cross the halt -- the dump is the step
    after it -- and ``Debugger.run`` did not, so it reported ``"halted"``
    with the answer one un-taken step away.  Reading it back meant knowing
    to call ``step()`` after a method that had already said it was done,
    and the CLI's ``debug`` did not know: it printed ``output: ''`` for a
    program that had run correctly, with no flag that reached the answer.
    """

    @staticmethod
    def _dumping() -> list[str]:
        """The languages whose answer arrives after the halt, from the data."""
        return [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["dumps_on_the_post_halt_step"]
        ]

    def test_the_set_is_the_seven(self) -> None:
        """Named from the registry, and not the six of a *different* set.

        ``answer_mode == "dump"`` also has six members and is not this one:
        it includes A Painter Ant and excludes ArrowQueue and Point Break.
        A docstring quoted that six for this set and was wrong by one.
        """
        assert len(self._dumping()) == 7
        mode = {
            n
            for n in esolangs.list_languages()
            if esolangs.describe(n)["answer_mode"] == "dump"
        }
        assert len(mode) == 6
        assert mode != set(self._dumping())

    def test_run_leaves_the_output_in_place(self) -> None:
        """All seven, since the bug was invisible on the other sixty-two."""
        empty = []
        for name in self._dumping():
            program = esolangs.generate(name, "0110")
            if esolangs.describe(name)["parameterized"]:
                program, stdin = esolangs.instantiate(name, program, [0, 0]), ""
            else:
                stdin = esolangs.encode_inputs(name, [0, 0], "0110")
            debugger = esolangs.make_debugger(name, program, stdin)
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
                stdin = esolangs.encode_inputs(name, [0, 0], "0110")
            debugger = esolangs.make_debugger(name, program, stdin)
            debugger.run(timeout=30)
            assert debugger.output == esolangs.run(name, program, stdin, 30), name

    def test_an_ordinary_language_takes_no_extra_step(self) -> None:
        """The step is a no-op elsewhere, but it would land in every watch.

        A bound that is not needed should not be spent, so the crossing is
        conditional -- and this is what says so.
        """
        debugger = esolangs.make_debugger("brainfuck", "+++.", "")
        history = debugger.watch_cell(0)
        debugger.run(timeout=10)
        assert len(history) == 4  # three increments and the print, no more


class TestTheDebuggerWarnsAboutStdinToo:
    """``run`` warned and the debugger did not, which is backwards.

    The warning exists for a wrong answer produced in silence: an underfed
    program on one of the languages where the end of input is a *value*
    answers a different row.  The debugger is the tool you reach for
    because you already suspect a wrong answer, and it was the one that
    would not name the commonest cause of one.
    """

    def test_the_debugger_says_what_run_says(self) -> None:
        """DINAC under-fed: one line to a two-input program."""
        program = esolangs.generate("DINAC", "0110")
        with pytest.warns(esolangs.InputMismatchWarning, match="read past the end"):
            esolangs.run("DINAC", program, "1\n", 10)
        with pytest.warns(esolangs.InputMismatchWarning, match="read past the end"):
            esolangs.make_debugger("DINAC", program, "1\n").run(timeout=10)

    def test_a_correct_input_stays_silent(self) -> None:
        """A warning that fires on correct input is worth less than none."""
        program = esolangs.generate("DINAC", "0110")
        stdin = esolangs.encode_inputs("DINAC", [1, 0], "0110")
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            esolangs.make_debugger("DINAC", program, stdin).run(timeout=10)

    def test_it_is_said_once(self) -> None:
        """``run`` on a halted machine returns at once; re-warning is noise."""
        program = esolangs.generate("DINAC", "0110")
        debugger = esolangs.make_debugger("DINAC", program, "1\n")
        with pytest.warns(esolangs.InputMismatchWarning):
            debugger.run(timeout=10)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            debugger.run(timeout=10)


class TestSelfHaltsIsAWarningNotAGuarantee:
    """``False`` used to promise the step loop never returns.  It can.

    Suffolk has no halt instruction and ends when a read runs out of input,
    so the obvious ``while not vm.halted: vm.step()`` returns on a program
    that reads and never on one that does not.  A Painter Ant, the other
    ``False``, genuinely runs forever.  The two disagree about the sentence
    the trait was described by, and what they share is that neither program
    text contains a halt -- so the bound has to come from outside.
    """

    def test_suffolk_halts_under_a_bare_step_loop(self) -> None:
        """The refutation, run rather than asserted."""
        assert esolangs.describe("Suffolk")["self_halts"] is False
        program = esolangs.generate("Suffolk", "0110")
        vm = esolangs.make_vm(
            "Suffolk", program, esolangs.encode_inputs("Suffolk", [1, 0])
        )
        steps = 0
        while not vm.halted and steps < 100_000:
            vm.step()
            steps += 1
        assert vm.halted, "Suffolk did not halt, so the old wording was right"
        assert vm.output == "1"

    def test_the_docstring_no_longer_promises_otherwise(self) -> None:
        """The wording is the fix, so the wording is what is checked."""
        doc = esolangs.VM.self_halts.__doc__ or ""
        assert "does not promise" in doc
        assert "Suffolk" in doc
