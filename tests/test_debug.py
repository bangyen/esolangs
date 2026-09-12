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


class TestEdges:
    """The bounds and the slot arithmetic, pinned where they turn over.

    A mutation sweep over ``debug.py`` -- the first this module has had --
    left six survivors, and all six were here.  Two shapes account for
    them.  Every bound was asserted far outside itself: ``watch_cell(9)``
    on a one-cell tape says nothing about ``index < len(memory)`` versus
    ``<=``, because both refuse a 9.  And every stack test used slot 0,
    where ``-1 - slot`` and ``-1 + slot`` are the same expression.
    """

    def test_no_input_means_no_input(self) -> None:
        """``stdin`` defaults to nothing, not to something.

        Nothing pinned the default, so it could have been any string: the
        programs the other tests build never read.
        """
        dbg = esolangs.make_debugger("brainfuck", ",")
        with pytest.raises(EOFError):
            dbg.step()

    def test_watching_the_cell_just_past_the_tape_is_absent(self) -> None:
        # One past the end, where a widened bound indexes out of range
        # instead of reporting the cell does not exist yet.
        dbg = esolangs.make_debugger("brainfuck", "+")
        history = dbg.watch_cell(1)
        dbg.step()
        assert history == [None]

    def test_breaking_on_the_cell_just_past_the_tape_never_fires(self) -> None:
        dbg = esolangs.make_debugger("brainfuck", "+")
        dbg.break_on_cell(1, 0)
        dbg.run()
        assert dbg.halted

    def test_watching_a_slot_below_the_top(self) -> None:
        """Slot 1 is the second value down, not the bottom of the stack.

        The two readings agree at slot 0 and on a two-deep stack, so this
        needs three distinct values to say anything at all.
        """
        dbg = esolangs.make_debugger("BFStack", ">+>++>+++")
        history = dbg.watch_stack(1)
        dbg.run()
        assert dbg.stack == [1, 2, 3]
        assert history[-1] == 2

    def test_breaking_on_a_slot_below_the_top(self) -> None:
        dbg = esolangs.make_debugger("BFStack", ">+>++>+++")
        dbg.break_on_stack(1, 2)
        dbg.run()
        assert not dbg.halted
        assert dbg.stack[-2] == 2

    def test_watching_the_slot_just_past_the_stack_is_absent(self) -> None:
        dbg = esolangs.make_debugger("BFStack", ">+")
        history = dbg.watch_stack(1)
        dbg.step()
        dbg.step()
        assert history == [None, None]


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


def _dumpers() -> list[str]:
    """Return the languages whose output lands one step past the halt."""
    return [
        name
        for name in esolangs.list_languages()
        if esolangs.describe(name)["dumps_on_the_post_halt_step"]
    ]


def _runnable(name: str, table: str = "0110") -> tuple[str, str]:
    """Return a filled program and the stdin to drive it with.

    The bits are ``[0, 0]``, whose XOR is 0, because two of the dumping
    languages answer by *terminating* -- they halt for a 0 and run forever
    for a 1.  Driven with bits answering 1 they never reach the halt these
    tests are about, and the runs come back ``"max_steps"``.
    """
    program = esolangs.generate(name, table)
    if esolangs.describe(name)["parameterized"]:
        return esolangs.instantiate(name, program, [0, 0]), ""
    return program, esolangs.encode_inputs(name, [0, 0])


class TestABreakpointAtTheHaltIsReported:
    """``run`` reported ``"halted"`` over a watch that had fired.

    A breakpoint is checked before each step, so a condition the *last*
    step makes true was never looked at.  The generated brainfuck XOR ends
    in ``.``, which makes watching for its answer the ordinary case rather
    than a corner.
    """

    def test_an_output_watch_on_the_last_step_fires(self) -> None:
        """The case it was reported for, on the flagship language."""
        dbg = esolangs.make_debugger(
            "brainfuck", esolangs.generate("brainfuck", "0110"), stdin="1\n0\n"
        )
        dbg.break_on_output("1")
        assert dbg.run(max_steps=100_000) == "breakpoint"
        assert dbg.run(max_steps=100_000) == "halted"
        assert dbg.halted

    @pytest.mark.parametrize("name", _dumpers())
    def test_a_pre_dump_condition_fires_on_every_dumper(self, name: str) -> None:
        """Checked on *both* sides of the post-halt dump step, not one.

        Checking only afterwards swallowed every predicate that reads the
        state before it: ``halted and output == ""`` was true at the halt,
        false one step later, and reported as ``"halted"``.
        """
        program, stdin = _runnable(name)
        dbg = esolangs.make_debugger(name, program, stdin=stdin)
        dbg.break_when(lambda vm: vm.halted and vm.output == "")
        assert dbg.run(max_steps=300_000) == "breakpoint"
        assert dbg.halted
        assert dbg.output == ""

    @pytest.mark.parametrize("name", _dumpers())
    def test_the_answer_is_never_stranded_by_that_stop(self, name: str) -> None:
        """A stop before the dump must not cost the caller the answer.

        Resuming is what takes it, so the reason -- not ``halted`` -- is
        what says whether the output is written yet.
        """
        program, stdin = _runnable(name)
        dbg = esolangs.make_debugger(name, program, stdin=stdin)
        dbg.break_when(lambda vm: vm.halted and vm.output == "")
        dbg.run(max_steps=300_000)
        assert dbg.run(max_steps=300_000) == "halted"
        assert dbg.output == esolangs.run(name, program, stdin, timeout=30)

    @pytest.mark.parametrize("name", _dumpers())
    def test_the_dump_step_is_taken_once_not_once_per_run(self, name: str) -> None:
        """Three idle runs grew a watch history by three.

        ``watch_cell`` promises the list grows one per ``step()``, and an
        already-halted, already-dumped machine takes no step at all.
        """
        program, stdin = _runnable(name)
        dbg = esolangs.make_debugger(name, program, stdin=stdin)
        history = dbg.watch_cell(0)
        dbg.run(max_steps=300_000)
        after_one = len(history)
        for _ in range(4):
            dbg.run(max_steps=300_000)
        assert len(history) == after_one


def _step_to_halt(dbg: esolangs.Debugger, budget: int = 200_000) -> None:
    """Drive ``dbg`` with ``step()`` alone until it halts.

    A plain loop, factored out so it can sit inside a ``pytest.raises``
    block as one statement.  ``step()`` rather than ``run()`` is the whole
    point of the tests that call it: the two modes reported an underfed
    stdin differently.
    """
    for _ in range(budget):
        if dbg.halted:
            return
        dbg.step()


class TestSteppingWarnsAboutStdinToo:
    """The warning fired under ``run`` and not under ``step``.

    Backwards: six languages take an exhausted read as a value and answer a
    different row, and ``step`` is the mode a debugging session drives
    with.  An underfed Fargo stepped to its halt returned a confident
    ``'0'`` and said nothing.
    """

    @staticmethod
    def _eof_is_a_value() -> list[str]:
        """The languages that carry on, which is the set that must warn.

        Alight is flagged ``eof_is_a_value`` and is not one of them: it
        refuses instead, which is the safe outcome and a different claim.
        It has its own test below rather than a branch in this sweep.
        """
        return [
            name
            for name in esolangs.list_languages()
            if esolangs.describe(name)["eof_is_a_value"]
            and not esolangs.describe(name)["parameterized"]
            and name != "Alight"
        ]

    @pytest.mark.parametrize("name", _eof_is_a_value.__func__())  # type: ignore[attr-defined]
    def test_stepping_to_the_halt_warns(self, name: str) -> None:
        """Fed one line short, which is the case the flag is about.

        An *empty* stdin is a different question -- several of these
        diverge before reaching the read at all -- so the input here is
        short by one line rather than absent.
        """
        program = esolangs.generate(name, "0110")
        full = esolangs.encode_inputs(name, [1, 0])
        lines = full.split("\n")
        short = "\n".join(lines[:-2]) + "\n" if len(lines) > 2 else ""
        if short == full:
            pytest.skip(f"{name} cannot be underfed by a line")
        dbg = esolangs.make_debugger(name, program, stdin=short)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _step_to_halt(dbg)
            dbg.step()
        assert any(
            issubclass(w.category, esolangs.InputMismatchWarning) for w in caught
        ), f"{name} stepped to its halt underfed and said nothing"

    def test_alight_refuses_instead_of_warning(self) -> None:
        """The documented exception, pinned so it stays a *loud* one.

        Alight is flagged ``eof_is_a_value``, which promises an underfed
        program carries on and answers a different row.  It does not: the
        sentinel reaches its arithmetic and it halts.  Refusing is the safe
        half of the two outcomes, so this is fine -- but it is fine only
        while it stays loud, and a change that made it carry on silently
        would be the wrong answer the flag warns about.
        """
        program = esolangs.generate("Alight", "0110")
        full = esolangs.encode_inputs("Alight", [1, 0])
        short = "\n".join(full.split("\n")[:-2]) + "\n"
        dbg = esolangs.make_debugger("Alight", program, stdin=short)
        with pytest.raises(esolangs.HaltError, match="eof"):
            _step_to_halt(dbg)
