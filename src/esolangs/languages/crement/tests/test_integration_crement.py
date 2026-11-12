"""Proof transport retains immutable instructions and unbounded integers."""

import json

import pytest

from esolangs.runtime._isolated import termination_result_isolated
from esolangs.runtime._result_wire import decode_decision, encode_decision
from esolangs.runtime._termination import _termination_result


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

    encoded["cycle"]["state"]["record"]["name"] = "_Machine"
    with pytest.raises(ValueError, match="undeclared immutable snapshot record"):
        decode_decision(encoded)
