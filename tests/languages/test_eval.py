"""Eval through the shared API, CLI and machinery."""

import esolangs.debugger as debugger_api


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
