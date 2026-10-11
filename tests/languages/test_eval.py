"""Eval through the shared API, CLI and machinery."""

import esolangs.debugger as debugger_api
from tests.reference import REFERENCE


class TestBreakpoints:
    def test_break_at_stops_before_target(self) -> None:
        dbg = debugger_api.make_debugger(
            REFERENCE,
            "+++>+++<-.",
        )
        dbg.break_at(3)
        dbg.run()
        assert dbg.ip == 3
        assert dbg.memory == [3]
        assert not dbg.halted

    def test_break_at_zero_fires_immediately(self) -> None:
        dbg = debugger_api.make_debugger(REFERENCE, "+")
        dbg.break_at(0)
        dbg.run()
        assert dbg.ip == 0
        assert dbg.memory == [0]  # the initial cell, not yet incremented

    def test_break_on_cell(self) -> None:
        dbg = debugger_api.make_debugger(REFERENCE, "+++++>++")
        dbg.break_on_cell(0, 5)
        dbg.run()
        assert dbg.memory == [5]  # stops before the '>' moves the pointer

    def test_break_on_cell_beyond_tape_does_not_fire(self) -> None:
        # the watch index never exists, so the run completes
        dbg = debugger_api.make_debugger(REFERENCE, "+")
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
        dbg = debugger_api.make_debugger(REFERENCE, "+++.")
        dbg.break_on_output("\x03")
        dbg.run()
        assert dbg.output == "\x03"

    def test_break_when_generic(self) -> None:
        dbg = debugger_api.make_debugger(REFERENCE, "++")
        dbg.break_when(lambda vm: vm.memory[0] == 1)
        dbg.run()
        assert dbg.memory == [1]
