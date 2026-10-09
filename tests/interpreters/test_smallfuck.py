"""Smallfuck fixed-tape semantics."""

import itertools
import random
from functools import partial

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.smallfuck import _Machine, run
from tests.interpreters.runner import run_program
from tests.interpreters.semantic_oracles import STDINS, agrees
from tests.interpreters.semantic_oracles import smallfuck as oracle

_run = partial(run_program, run, suppress_eof=False)


def test_flip_move_loop_and_final_tape() -> None:
    machine = _Machine("*>*[*]", ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert machine.memory == [1, 0, 0, 0, 0, 0]


@pytest.mark.parametrize("source", ["<*", ">>"])
def test_crossing_a_tape_end_halts(source: str) -> None:
    assert _run(source) == "0"


def test_noncommands_are_ignored_but_take_tape_cells() -> None:
    machine = _Machine("*x", ScriptedIO(""))
    while not machine.halted:
        machine.step()
    assert machine.memory == [1, 0]


def test_halted_step_dumps_once() -> None:
    io = ScriptedIO("")
    machine = _Machine(">>*", io)
    machine.step()
    machine.step()
    machine.step()
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
def test_bounded_programs_match_the_oracle(stdin):
    for code in _corpus():
        agrees(_Machine, oracle, code, stdin, dump=True)


@pytest.mark.parametrize(
    ("code", "output"),
    [("[", None), ("]", None), ("][", None), (">>*", "1"), ("<", "0"), (">", "0")],
)
def test_oracle_controls(code, output):
    result = agrees(_Machine, oracle, code, "\x81", dump=True)
    assert result.output == output if output else isinstance(result, ValueError)
    assert not agrees(_Machine, oracle, "*[]", "", dump=True).halted
