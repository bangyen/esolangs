"""Tests for the breakpoint/watch debugger over the VM."""

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
        assert dbg.ip == 1
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
        dbg = esolangs.make_debugger("brainfuck", "+")
        first = dbg.watch_cell(0)
        dbg.step()
        assert first == [1]

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
