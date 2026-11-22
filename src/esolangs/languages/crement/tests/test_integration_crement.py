"""Proof transport retains immutable instructions and unbounded integers."""

import json
import sys

import pytest

from esolangs import ExecutionLimits, Language, TemplateArtifact, TemplateBindings
from esolangs.runtime._isolated import termination_result_isolated
from esolangs.runtime._result_wire import decode_decision, encode_decision
from esolangs.runtime._termination import _termination_result
from esolangs.vm import _capture_workspace


@pytest.mark.medium
def test_a_large_integer_cycle_retains_declared_record_types():
    source = "+J 0 " + "1" + "0" * 5000
    native = _termination_result("Crement", source, "")
    assert native.decision.halts is False
    assert native.decision.commands == 1
    encoded = json.loads(json.dumps(encode_decision(native.decision)))
    assert decode_decision(encoded) == native.decision
    assert native.decision.cycle.state.program[0].data == 10**5000
    assert termination_result_isolated("Crement", source, "", 5) == native

    encoded["cycle"]["state"]["define"][1]["record"]["name"] = "_Machine"
    with pytest.raises(ValueError, match="undeclared immutable snapshot record"):
        decode_decision(encoded)


@pytest.mark.medium
def test_debug_and_proof_repr_preserve_large_crement_values() -> None:
    api = Language("Crement")
    digits = "1" + "0" * 5000
    spelling = hex(10**5000)
    template = TemplateArtifact(
        "+J 0 " + digits,
        api.name,
        TemplateBindings(setters=(("", ""),)),
        spans=((0, 0),),
    )
    local = api.evaluate(template, [0], limits=ExecutionLimits(max_steps=2))
    worker = api.evaluate(
        template, [0], limits=ExecutionLimits(max_steps=2, total_timeout=5)
    )
    assert local == worker
    assert local.termination.commands == 1
    vm = api.make_debugger(template.fill([0]))
    cap = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        assert f"data={spelling}" in repr(vm.snapshot())
        assert f"data={spelling}" in repr(worker)
        assert spelling in repr(_capture_workspace(vm.vm))
        jumping = api.make_debugger("+J " + digits + " 1")
        jumping.step()
        assert jumping.halted
        assert f"ip={spelling}" in repr(jumping.snapshot())
    finally:
        sys.set_int_max_str_digits(cap)
    assert repr(api.make_debugger("+J 0 1").snapshot()) == (
        "_State(ip=0, program=(_Instruction(opcode='J', polarity=1, "
        "address=0, data=1),))"
    )
