"""Smallfuck fixed-tape semantics."""

import itertools
import random

import pytest

from esolangs.languages.smallfuck import interpreter as native
from esolangs.languages.smallfuck.interpreter import _advance, _Machine, run
from esolangs.languages.smallfuck.tests.oracle_checks import _WORKSPACE, check, oracle
from esolangs.runtime.io import ScriptedIO
from tests.interpreters.runner import native_runner
from tests.interpreters.semantic_oracles import STDINS, agrees
from tests.support.prepared_support import check_image_reuse
from tests.support.workspace_oracle import charged_bits, check_erasures

_run = native_runner(run)


@pytest.mark.parametrize(
    ("source", "memory"), [("*>*[*]", [1, 0, 0, 0, 0, 0]), ("*x", [1, 0])]
)
def test_flip_move_loop_and_final_tape(source, memory) -> None:
    machine = _Machine(source, ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert machine.memory == memory


@pytest.mark.parametrize("source", ["<*", ">>"])
def test_crossing_a_tape_end_halts(source: str) -> None:
    assert _run(source) == "0"


def test_halted_step_dumps_once(monkeypatch: pytest.MonkeyPatch) -> None:
    io = ScriptedIO("")
    machine = _Machine(">>*", io)
    machine.step()
    machine.step()
    machine.step()
    before = machine.snapshot(), machine.workspace_snapshot()
    machine.step()
    assert machine.snapshot() == before[0]
    assert machine.workspace_snapshot().parts == (*before[1].parts[:3], True)
    assert before[1].parts[-1] is False
    assert io.getvalue() == "1"
    check_image_reuse(
        "Smallfuck",
        ">>*[*]",
        native,
        "_prepare_source",
        monkeypatch,
        cases=(("", "0"),) * 3,
    )
    machine.step()
    assert io.getvalue() == "1"


def test_machine_exposes_pointer_and_tape() -> None:
    machine = _Machine(">*", ScriptedIO(""))
    machine.step()
    machine.step()
    assert (machine.ptr, machine.tape) == (1, (0, 1))


@pytest.mark.parametrize("source", ["[", "]"])
def test_unbalanced_loops_are_rejected(source: str) -> None:
    with pytest.raises(ValueError, match="unmatched"):
        _run(source)


def _corpus():
    for n in range(5):
        yield from ("".join(c) for c in itertools.product("*<>", repeat=n))
    yield from ["", "[]", "*[**]", "*[]", ">>*", "*[>*<*]", "[ignored]", "<*", ">"]
    rng = random.Random(1703)
    for _ in range(64):
        yield "".join(rng.choices(["*", "<", ">", "[**]", "[>*<*]", "[]"], k=8))


@pytest.mark.parametrize("stdin", STDINS)
def test_bounded_programs_match_the_oracle(stdin) -> None:
    for code in _corpus():
        agrees(_Machine, oracle, code, stdin, dump=True)
        check(_Machine, code, stdin)


@pytest.mark.parametrize(
    ("code", "output"),
    [("[", None), ("]", None), ("][", None), (">>*", "1"), ("<", "0"), (">", "0")],
)
def test_oracle_controls(code, output) -> None:
    result = agrees(_Machine, oracle, code, "\x81", dump=True)
    assert result.output == output if output else isinstance(result, ValueError)
    assert not agrees(_Machine, oracle, "*[]", "", dump=True).halted
    if code == ">>*":
        check_erasures(_WORKSPACE, check, _Machine, ">>*", "")
        for source, bits in (
            ("", 1),
            ("<", 2),
            (">", 3),
            ("*", 3),
            ("*x", 5),
            (">>*", 8),
        ):
            rows = check(_Machine, source, "untouched")
            assert charged_bits(_WORKSPACE, (row[0] for row in rows)) == bits


def test_transition_preserves_its_state_and_reports_output() -> None:
    machine = _Machine(">>*", ScriptedIO(""))
    state = machine.state
    first = _advance(state, machine.code, machine.brackets)
    assert _advance(state, machine.code, machine.brackets) == first
    assert machine.state == state
    assert machine.io.getvalue() == ""
    halted = (3, 2, (0, 0, 1), False)
    assert _advance(halted, machine.code, machine.brackets) == (
        (3, 2, (0, 0, 1), True),
        "1",
    )
