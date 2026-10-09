"""ArrowQueue through the shared API, CLI and machinery."""

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs._evaluate import _evaluate


def test_termination_input_exhaustion_is_a_fault(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import esolangs._evaluate as evaluate_module

    def exhausted(*_args: object, **_kwargs: object) -> None:
        raise esolangs.InputExhaustedError(2, 1)

    program = esolangs.generate("ArrowQueue", "01")
    monkeypatch.setattr(evaluate_module, "make_vm", exhausted)
    with pytest.raises(esolangs.InputExhaustedError) as exc:
        _evaluate("ArrowQueue", program, inputs=1)
    assert any("row 0" in note for note in exc.value.__notes__)


class TestArrowQueue:
    def test_ip_is_position_and_heading(self) -> None:
        vm = debugger_api.make_vm("ArrowQueue", "~+*")
        assert vm.ip == (0, 0, 0)
        vm.step()
        assert vm.ip == (0, 1, 0)
        assert vm.stack == [0]
        vm.step()  # + pops the queued direction (right) and keeps going
        assert vm.ip == (0, 2, 0)
        assert vm.stack == []
        vm.step()  # * turns down off the single row and halts
        assert vm.halted
        assert vm.memory == []
        vm.step()  # stepping a halted VM is a no-op
