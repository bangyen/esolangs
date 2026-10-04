"""LaserFuck EOF witnesses and generated-program provenance."""

import pytest

import esolangs
from esolangs import DialectSettings
from esolangs._laserfuck import LaserfuckDialect
from esolangs.interpreters.grid_based.laserfuck import _Machine, run
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.persistent import flatten
from esolangs.interpreters.randomness import FirstDraw
from esolangs.tagged import _Tagged
from esolangs.tools.laserfuck import laserfuck
from esolangs.vm import complete_vm, make_vm


@pytest.mark.parametrize(
    ("policy", "expected"), [("zero", 0), ("minus_one", -1), ("unchanged", 1)]
)
def test_input_transition_and_vm(policy, expected):
    machine = _Machine(["o+,x"], ScriptedIO(), FirstDraw(3), eof=policy)
    while not machine.halted:
        machine.step()
    assert flatten(machine.tape) == ((expected, 1),)
    settings = DialectSettings(eof=policy)
    vm = make_vm("LaserFuck", " }+,x\n|o^\n _", settings=settings)
    assert complete_vm(vm, 20) == ("" if expected < 0 else str(expected))
    assert esolangs.run("LaserFuck", " }+,x\n|o^\n _", settings=settings, seed=2) == (
        "" if expected < 0 else str(expected)
    )


@pytest.mark.parametrize("policy", ["error", "zero", "minus_one", "unchanged"])
def test_successful_input_and_default_error(policy):
    io = ScriptedIO("A")
    run(["o+,x"], io, FirstDraw(3), eof=policy)
    assert io.getvalue() == "65"
    with pytest.raises(EOFError):
        run(["o,x"], ScriptedIO(), FirstDraw(3))


def test_invalid_policy_and_metadata():
    with pytest.raises(ValueError, match="eof"):
        LaserfuckDialect("bad")
    with pytest.raises(ValueError, match="eof"):
        laserfuck("01", eof="bad")
    with pytest.raises(esolangs.ArgumentError):
        esolangs.run("LaserFuck", "o,x", settings=DialectSettings(eof="bad"))
    assert (
        esolangs.describe("LaserFuck")["dialect_settings"]["eof"]["default"] == "error"
    )


@pytest.mark.medium
@pytest.mark.parametrize("policy", ["error", "zero", "minus_one", "unchanged"])
@pytest.mark.parametrize("chunk", range(16))
def test_generated_corpus(policy, chunk):
    settings = DialectSettings(eof=policy)
    for inputs in range(1, 4):
        for value in range(chunk, 1 << (1 << inputs), 16):
            table = format(value, f"0{1 << inputs}b")
            for balanced in (False, True):
                source = esolangs.generate(
                    "LaserFuck", table, balance=balanced, settings=settings
                )
                assert esolangs.evaluate("LaserFuck", source, inputs=inputs) == table


@pytest.mark.medium
def test_portable_isolation_and_override():
    source = esolangs.generate(
        "LaserFuck", "0110", settings=DialectSettings(eof="zero")
    )
    saved = esolangs.load_program(
        "LaserFuck", esolangs.dump_program("LaserFuck", source)
    )
    assert esolangs.evaluate("LaserFuck", saved, inputs=2, isolated=True) == "0110"
    witness = _Tagged(
        " }+,x\n|o^\n _", "LaserFuck", settings=DialectSettings(eof="unchanged")
    )
    saved = esolangs.load_program(
        "LaserFuck", esolangs.dump_program("LaserFuck", witness)
    )
    assert esolangs.run("LaserFuck", saved, seed=2) == "1"
    assert (
        esolangs.run("LaserFuck", saved, seed=2, settings=DialectSettings(eof="zero"))
        == "0"
    )


def test_unchanged_preserves_untouched_cell():
    io = ScriptedIO()
    machine = _Machine(["o,x"], io, FirstDraw(3), eof="unchanged")
    while not machine.halted:
        machine.step()
    machine.dump()
    assert flatten(machine.tape) == ((0, 0),)
    assert io.getvalue() == ""


def test_cli_portable_eof_and_override(tmp_path, capsys):
    from tests.cli_support import call_both

    source = _Tagged(" }+,x\n|o^\n _", "LaserFuck", DialectSettings(eof="unchanged"))
    path = tmp_path / "laserfuck-eof.json"
    path.write_text(esolangs.dump_program("LaserFuck", source))
    args = ["run", "--portable", "--seed", "2"]
    output, error = call_both([*args, "LaserFuck", str(path)], capsys)
    assert output.strip() == "1"
    assert error == ""
    output, error = call_both(
        [*args, "--settings", '{"eof":"zero"}', "LaserFuck", str(path)], capsys
    )
    assert output.strip() == "0"
    assert error == ""
