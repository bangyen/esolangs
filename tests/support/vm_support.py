"""Reusable vm support helpers."""

from __future__ import annotations

import contextlib
import sys
from dataclasses import replace
from typing import Literal

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.results import Completion
from esolangs.runtime._vm_protocol import VM
from esolangs.vm import _capture_result, complete_vm
from tests.support.reference import REFERENCE


def _step_to_halt(dbg: debugger_api.Debugger, budget: int = 200_000) -> None:
    """Drive ``dbg`` with ``step()`` alone until it halts."""
    for _ in range(budget):
        if dbg.halted:
            return
        dbg.step()


def assert_vm_finalization_is_shared(
    language: str,
    source: str,
    steps: int,
    output: str,
    finalize: Literal["step", "complete_vm"],
    *,
    seed: int | None = None,
) -> None:
    """Share a VM's finalization with debuggers while keeping their step counts."""
    vm = debugger_api.make_vm(language, source, seed=seed)
    before = debugger_api.Debugger(vm)
    for _ in range(steps):
        before.step()
    assert vm.halted
    assert before.observation.completion is None
    with pytest.raises(esolangs.ArgumentError, match="completed post-halt dump"):
        _capture_result(vm)
    if finalize == "step":
        vm.step()
    else:
        assert complete_vm(vm, max_steps=0) == output

    after = debugger_api.Debugger(vm)
    expected = esolangs.run(
        language, source, seed=seed, limits=esolangs.ExecutionLimits(max_steps=steps)
    )
    assert expected.output == output
    assert expected.completion.kind is Completion.POST_HALT
    assert _capture_result(vm) == replace(expected, steps=None)
    for debugger, observed in ((before, expected), (after, replace(expected, steps=0))):
        watch = debugger.watch_cell(0)
        assert debugger.observation == observed
        assert debugger.run(limits=esolangs.ExecutionLimits(max_steps=0)) == "halted"
        assert debugger.observation == observed
        assert watch == []


def assert_one_row_moves_along_it(name: str) -> None:
    """``name`` lays its generated program on one row and moves along it.

    Each such language calls this from its own test file.
    """
    program, stdin = _row_for(name)
    assert program.source.count("\n") == 0, name  # one row
    assert _first_move(name, program, stdin)[0] == 0, name


def assert_starts_downward(name: str, width: int | None = None) -> None:
    """``name``'s generated program first moves in the row component.

    Each language that begins vertically calls this from its own test file.
    """
    program, stdin = _row_for(name, width)
    before, after = _first_move_pair(name, program, stdin)
    assert before[0] != after[0], name
    assert before[1] == after[1], name


def _row_for(
    name: str, width: int | None = None
) -> tuple[esolangs.ProgramArtifact[esolangs.Program], str]:
    """A runnable program and its stdin for a two-input table."""
    table = "0110"
    program = (
        esolangs.generate(name, table)
        if width is None
        else esolangs.generate(name, table, width=width)
    )
    if esolangs.describe(name).parameterized:
        return esolangs.instantiate(name, program, [0, 0]), ""
    return program, esolangs.encode_inputs(name, [0, 0], truth_table=table)


def _first_move_pair(
    name: str, program: esolangs.ProgramSource, stdin: str
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """The coordinate before and after the first move that changes it."""
    vm = debugger_api.make_vm(name, program, stdin=stdin)
    start = vm.ip
    assert isinstance(start, tuple)
    for _ in range(400):
        if vm.halted:
            break
        vm.step()
        here = vm.ip
        if isinstance(here, tuple) and len(here) >= 2 and here[:2] != start[:2]:
            return start[:2], here[:2]
    raise AssertionError(f"{name} never moved")


def _first_move(
    name: str, program: esolangs.ProgramSource, stdin: str
) -> tuple[int, int]:
    """Which components changed on the first move, as a (row, col) pair."""
    before, after = _first_move_pair(name, program, stdin)
    return (before[0] != after[0], before[1] != after[1])


def assert_random_steps_reproduce(language: str, program: str) -> None:
    """A random instruction in ``program`` runs, and steps the same way twice.

    Each random language calls this from its own test file with a program
    that reaches its random instruction.
    """
    from esolangs.runtime import randomness

    def trace() -> list[object]:
        vm = debugger_api.make_vm(language, program)
        seen: list[object] = []
        for _ in range(40):
            if vm.halted:
                break
            with contextlib.suppress(Exception):
                vm.step()
            ip = vm.ip
            seen.append((tuple(ip) if isinstance(ip, tuple) else ip, tuple(vm.memory)))
        return seen

    original = randomness.Seeded.randbelow
    drawn: list[int] = []

    def counted(self: randomness.Seeded, upper: int) -> int:
        drawn.append(upper)
        return original(self, upper)

    randomness.Seeded.randbelow = counted
    try:
        first = trace()
    finally:
        randomness.Seeded.randbelow = original
    assert drawn, f"{language}: the random instruction never ran"
    assert trace() == first, f"{language} is not reproducible"


def _run_all(vm: VM) -> str:
    while not vm.halted:
        vm.step()
    return vm.output


_STEP_BUDGET = 2_000_000


def _row(
    name: str, table: str, bits: list[int]
) -> tuple[esolangs.ProgramArtifact[esolangs.Program], str]:
    """Return the ``(program, stdin)`` for one row, without naming a language."""
    if esolangs.describe(name).parameterized:
        return esolangs.instantiate(name, esolangs.generate(name, table), bits), ""
    return esolangs.generate(name, table), esolangs.encode_inputs(
        name, bits, truth_table=table
    )


def _debugger() -> debugger_api.Debugger:
    return debugger_api.make_debugger(REFERENCE, "+[]", stdin="")


_LINUX = sys.platform == "linux"


_BUDGET = 96 * 1024 * 1024
