"""Prepared Container rules, EOF values and legacy EXIT codes remain per-run."""

import pytest

from esolangs.languages.container import interpreter
from esolangs.runtime.io import ScriptedIO


def test_factory_binds_source_with_private_rules_and_tick_state():
    source = [":", "+1 EXIT>=0", "EXIT:", "+7 EXIT<=0"]
    factory = interpreter.prepare_machine(source, {})
    first, second = factory(ScriptedIO("A")), factory(ScriptedIO())
    source.clear()
    assert first.obj is not second.obj
    assert first.obj[0].rules == second.obj[0].rules
    assert first.obj[0].rules is not second.obj[0].rules
    before = second.snapshot()
    first.step()
    assert first.halted
    assert first.exit_code == 7
    assert first.var["IN"] == 65
    assert first.tick == 1
    assert second.snapshot() == before
    assert second.tick == 0
    first.obj[0].rules.clear()
    third = factory(ScriptedIO())
    assert third.obj[0].rules == second.obj[0].rules
    assert third.snapshot() == before
    second.step()
    assert second.halted
    assert second.exit_code == 7
    assert second.var["IN"] == 0
    assert second.state[3] == 0
    assert second.io.past_end == 1
    assert third.snapshot() == before

    for code, expected in (
        ([], None),
        (["EXIT:", "+7 EXIT<=0"], 7),
        (["EXIT=1:", "-1 EXIT>=1"], 0),
    ):
        assert interpreter.run(code, ScriptedIO()) == expected

    with pytest.raises(TypeError, match="split text"):
        interpreter.prepare_machine("EXIT:", {})
    with pytest.raises(TypeError, match="no runtime options"):
        interpreter.prepare_machine([], {"unexpected": True})
