"""Forþ through the shared API, CLI and machinery."""

import esolangs.debugger as debugger_api


class TestForth:
    def test_stack_and_active_frame_cursor(self) -> None:
        vm = debugger_api.make_vm("Forþ", "65.")
        assert vm.ip == (0,)
        assert vm.stack == []
        vm.step()  # 6 pushes
        assert (vm.ip, vm.stack) == ((1,), [6])
        vm.step()  # 5 pushes
        assert vm.stack == [6, 5]
        vm.step()  # . pops and prints the low byte
        assert vm.output == "\x05"
        vm.step()  # finalizing the finished frame halts the machine
        assert vm.halted
        assert vm.ip == (len("65."),)  # frames are gone once halted
        assert vm.memory == []

    def test_ip_exposes_the_call_stack(self) -> None:
        # '1{:}1;' stores the scope ':' under key 1, then calls it; ip
        # grows to (caller pc, callee pc) while the scope is active instead
        # of folding it into one cursor.
        vm = debugger_api.make_vm("Forþ", "1{:}1;")
        for _ in range(4):
            vm.step()
        assert vm.ip == (6, 0)  # caller's pc past ';', callee's pc at start
        assert vm.stack == [1]
        vm.step()  # the callee's ':' command runs (dup)
        assert vm.ip == (6, 1)
        assert vm.stack == [1, 1]
        vm.step()  # finalizing the finished callee frame halts the machine
        assert vm.halted
        assert vm.ip == (6,)  # the callee frame is gone once it returns
