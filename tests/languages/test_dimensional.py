"""Dimensional through the shared API, CLI and machinery."""

import esolangs.debugger as debugger_api


class TestDimensional:
    def test_byte_value_exposed(self) -> None:
        vm = debugger_api.make_vm("Dimensional", "++.")
        assert (vm.ip, vm.memory, vm.stack) == (0, [0], [])
        vm.step()
        assert vm.memory == [1]
        vm.step()
        assert vm.memory == [2]
        vm.step()
        assert vm.output == "\x02"
