"""S*bleq through the shared API, CLI and machinery."""

import pytest

import esolangs
import esolangs.debugger as debugger_api


@pytest.mark.medium
def test_memory_limit_has_an_address_hint():
    with pytest.raises(esolangs.InterpreterLimitError) as caught:
        esolangs.run("S*bleq", "100000000000000000000 0 0", timeout=1)
    assert "smaller memory addresses" in caught.value.__notes__[0]


def test_memory_address_at_the_cell_limit_is_refused():
    from esolangs._validate import _MAX_CELLS, check_address
    from esolangs.exceptions import InterpreterLimitError

    assert check_address(_MAX_CELLS - 1, "S*bleq") == _MAX_CELLS - 1
    for address in (_MAX_CELLS, _MAX_CELLS + 1):
        with pytest.raises(InterpreterLimitError, match="cell limit"):
            check_address(address, "S*bleq")


def test_oversized_memory_addresses_keep_the_allocation_error():
    from esolangs._validate import check_address

    with pytest.raises(esolangs.InterpreterLimitError, match="integer with"):
        check_address(10**5000, "S*bleq")


class TestSbleq:
    def test_oisc_cells_and_ip(self) -> None:
        vm = debugger_api.make_vm("S*bleq", "-3 11 3")
        assert (vm.ip, vm.memory, vm.stack) == (0, [-3, 11, 3], [])
        vm.step()
        assert (vm.ip, vm.halted, vm.output) == (3, True, "\x00")
