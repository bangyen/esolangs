"""Instruction-level NQ checks, including commands absent from generated code."""

import pytest

from esolangs.exceptions import ArgumentError, HaltError
from esolangs.languages.nq.interpreter import _Machine, run
from esolangs.runtime.io import ScriptedIO


def check_instructions() -> None:
    """Check grouping, first-lap loads, wrapping, I/O and failures."""
    for source, stdin, expected in [
        ("+(012)W-W-WH", "", " \n#"),
        ("RW-W-WH", "0 1\n2", " \n#"),
        ("R+2WH", "", "#"),
        ("r->1(+2WH)+0WH", "1", "#"),
        ("r->1(+2WH)+0WH", "0", " "),
        ("+0->0>0+2WH", "", "#"),
        ("+0->1>0+2WH", "", "#"),
        ("+0->1>0(+1)+2WH", "", "#"),
        ("+1->1(>0(+0WH)+2WH)+0WH", "", "#"),
        ("l(012)W-W-WH", "", " \n#"),
        ("xyz 9 ?", "", ""),
    ]:
        io = ScriptedIO(stdin)
        run(source, io)
        assert io.getvalue() == expected
    for source in ("+", "+3", "+(01x)", "+(01", ">", ">3", ">1("):
        with pytest.raises(ValueError, match=r"trit|guard|list"):
            _Machine(source, ScriptedIO())
    for source in ("WH", "-H", "r-WH"):
        with pytest.raises(HaltError):
            run(source, ScriptedIO("2"))
    for source in ("rH", "RH"):
        with pytest.raises(ArgumentError):
            run(source, ScriptedIO("x"))
    with pytest.raises(EOFError):
        run("rH", ScriptedIO(" \n"))
    io = ScriptedIO()
    run(">1(" * 2500 + "+2WH" + ")" * 2500 + "+0WH", io)
    assert io.getvalue() == " "
    for binding, expected in (("opcode", "#"), ("recursive", " ")):
        io = ScriptedIO()
        run("+0->1>0+2+0WH", io, guard_binding=binding)
        assert io.getvalue() == expected
    with pytest.raises(HaltError):
        run("+0->1>0+2WH", ScriptedIO(), guard_binding="recursive")
    for source in (">1", ">1(>0)H", ">1>0", ">0(>1)>2H"):
        with pytest.raises(ValueError, match="complete instruction"):
            _Machine(source, ScriptedIO(), guard_binding="recursive")
    with pytest.raises(ValueError, match="guard_binding"):
        _Machine("H", ScriptedIO(), guard_binding="bogus")
    machine = _Machine(">0" * 2500 + "H", ScriptedIO(), guard_binding="recursive")
    for _ in range(2501):
        machine.step()
    assert machine.halted
    io = ScriptedIO()
    machine = _Machine(">0(+2)W>1", io)
    for _ in range(4):
        machine.step()
    assert machine.ip == 6  # wrap skips the whole first group, not just >0
    assert machine.memory == [2]
    for _ in range(2):
        machine.step()
    assert machine.memory == [2]
    assert io.getvalue() == "##"
    machine = _Machine("l2W-", ScriptedIO())
    for _ in range(4):
        machine.step()
    assert machine.state.first is False
    assert machine.memory == []  # the load did not execute on the second lap
    with pytest.raises(HaltError):
        machine.step()
    machine = _Machine(">1", ScriptedIO())
    machine.step()
    assert machine.state.cursor == 0
    assert machine.state.first is False
    assert not machine.halted
    machine = _Machine("r-H", ScriptedIO("01"))
    initial = machine.snapshot()
    machine.step()
    assert machine.snapshot() != initial
    machine.step()
    assert machine.state.flag == 0
    assert machine.memory == []
    machine.step()
    final = machine.snapshot()
    machine.step()
    assert machine.snapshot() == final
