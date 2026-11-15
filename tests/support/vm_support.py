"""Reusable vm support helpers."""

from __future__ import annotations

import contextlib
import sys
from collections.abc import Callable
from dataclasses import replace
from typing import Literal

import pytest

import esolangs
import esolangs.debugger as debugger_api
from esolangs.results import Completion
from esolangs.runtime._source import ProgramSource
from esolangs.runtime._state import WorkspaceVariant
from esolangs.runtime._vm_protocol import VM
from esolangs.runtime.io import ScriptedIO
from esolangs.vm import (
    _capture_result,
    _capture_workspace,
    complete_vm,
    run_until_halt_or_cycle,
)
from tests.support.reference import REFERENCE


def _step_to_halt(dbg: debugger_api.Debugger, budget: int = 200_000) -> None:
    """Drive ``dbg`` with ``step()`` alone until it halts."""
    for _ in range(budget):
        if dbg.halted:
            return
        dbg.step()


def assert_proof_fault(
    detector: Callable[[VM, int], bool],
    language: str,
    source: str,
    error_type: type[esolangs.EsolangError],
    output: str,
    *,
    debugged: bool,
    stdin: str = "",
) -> None:
    """Compare a live detector's fault evidence with exact-cycle detection."""
    observations = []
    for decide in (run_until_halt_or_cycle, detector):
        vm = debugger_api.make_vm(language, source, stdin=stdin)
        runner = debugger_api.Debugger(vm) if debugged else vm
        with pytest.raises(error_type) as caught:
            decide(runner, 20)
        assert runner.output == caught.value.partial_output == output
        assert caught.value.observation is not None
        assert caught.value.observation.completion is None
        observations.append(caught.value.observation)
    assert observations[0] == observations[1]


def assert_rejected_input_retry(
    language: str,
    source: ProgramSource,
    stdin: str,
    valid: str,
    output: str,
    *,
    position: int,
    reads: int,
    rejected: str | Literal[True] | None = None,
    error_type: type[esolangs.EsolangError] = esolangs.ArgumentError,
    prefix: int = 0,
    partial: str = "",
) -> None:
    """Check rejected input in fresh runs, successive retries and the workspace."""
    api = esolangs.Language(language)
    prepared = api.prepare(source)
    limits = esolangs.ExecutionLimits(max_steps=64)
    assert prepared.run(stdin=valid, limits=limits).output == output
    reports = (
        api.execute(source, stdin=stdin),
        prepared.execute(stdin=stdin),
        api.execute(source, stdin=stdin, isolated=True),
    )
    fault = reports[0].error
    assert type(fault) is error_type
    notes = tuple(getattr(fault, "__notes__", ()))
    diagnostic = tuple(
        note for note in notes if not note.startswith("the program printed ")
    )
    details = error_type.__name__, str(fault), diagnostic
    expected = esolangs.ExecutionResult(partial, position, reads, 0)
    for report in reports:
        assert type(report.error) is error_type
        assert report.observation == expected
        assert report.error.args == fault.args
        assert tuple(getattr(report.error, "__notes__", ())) == notes

    dbg = prepared.make_debugger(stdin=stdin)
    for _ in range(prefix):
        dbg.step()
    ip, before = dbg.ip, dbg.snapshot()
    for resume in (dbg.step, lambda: dbg.run(limits=limits), dbg.step):
        with pytest.raises(error_type) as caught:
            resume()
        assert caught.value.args == fault.args
        assert tuple(getattr(caught.value, "__notes__", ())) == notes
        assert dbg.observation == replace(expected, steps=prefix)
        assert dbg.ip == ip
        after = dbg.snapshot()
        assert before[:-1] == after[:-2]
        assert after[-2:] == (position, details if rejected is None else rejected)
        values = () if rejected is True else (rejected,)
        data = (position, *(details if rejected is None else values))
        assert _capture_workspace(dbg.vm).parts[-1] == WorkspaceVariant(
            "rejected_input", data
        )


def assert_rejected_output_retry(
    name: str,
    source: str,
    value: int | str,
    output: str,
    *,
    prefix: int,
    monkeypatch: pytest.MonkeyPatch,
    stdin: str = "",
    unchanged_if_unwritten: bool = False,
    following_writes: tuple[int | str, ...] | None = None,
) -> None:
    """Resume a debugger after a sink accepts zero, some or all of a write."""
    language = esolangs.Language(name)
    limits = esolangs.ExecutionLimits(max_steps=32)
    expected = language.run(source, stdin=stdin, limits=limits)
    assert expected.output == output
    write = ScriptedIO._write
    text = str(value)

    def check(accepted: int) -> None:
        attempts: list[object] = []

        def refuse_first(io: ScriptedIO, payload: object) -> None:
            attempts.append(payload)
            if len(attempts) == 1:
                write(io, text[:accepted])
                raise esolangs.HaltError("temporary writer refusal")
            write(io, payload)

        with monkeypatch.context() as port:
            port.setattr(ScriptedIO, "_write", refuse_first)
            debugger = language.make_debugger(source, stdin=stdin)
            for _ in range(prefix):
                debugger.step()
            boundary = debugger.snapshot()
            before = debugger.observation
            was_halted = debugger.halted
            with pytest.raises(
                esolangs.HaltError, match="temporary writer refusal"
            ) as fault:
                debugger.run(limits=limits)
            partial = replace(before, output=before.output + text[:accepted])
            assert fault.value.observation == debugger.observation == partial
            assert debugger.halted is was_halted
            if unchanged_if_unwritten and not accepted:
                assert debugger.snapshot() == boundary
            else:
                assert debugger.snapshot() == (*boundary, accepted)
            assert debugger.run(limits=limits) == "halted"
            assert debugger.observation == expected
            assert fault.value.observation == partial
            assert type(attempts[0]) is type(value)
            assert attempts[0] == value
            pending = (
                (text[accepted:] if accepted else value,)
                if accepted < len(text) or not text
                else ()
            )
            if following_writes is not None:
                assert tuple(attempts[1:]) == pending + following_writes
            elif pending:
                assert tuple(attempts[1:2]) == pending

    for accepted in range(len(text) + 1):
        check(accepted)


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
