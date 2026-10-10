"""Shared frames preserve ordered paths and the evaluator's resource bounds."""

import pytest

import esolangs
from esolangs._answers import read_answer
from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.other.algebraic_programming_language import _Machine
from esolangs.tools.algebraic_programming_language import (
    _apl_reduced_ordered,
    _apl_split,
)
from scripts.benchmark import WrittenState
from tests.algebraic_programming_language.formulas import execution, workspace

NAME = "Algebraic Programming Language"


@pytest.mark.medium
@pytest.mark.parametrize(
    ("n", "band"), [(1, 0), (2, 0), (3, 0), (3, 1), (3, 2), (3, 3)]
)
def test_forced_shared_frames_obey_bounds_for_every_small_table(n, band):
    positive = 0
    span = 64 if n == 3 else 1 << (1 << n)
    for value in range(band * span, (band + 1) * span):
        table = f"{value:0{1 << n}b}"
        source = _apl_split(table, tuple(range(n)), 1, _apl_reduced_ordered)[0]
        for row, expected in enumerate(table):
            bits = [row >> shift & 1 for shift in range(n - 1, -1, -1)]
            machine = _Machine(source, ScriptedIO(esolangs.encode_inputs(NAME, bits)))
            original = machine._step_call  # noqa: SLF001
            calls = []

            def traced(frame, node, done, *, _calls=calls, _original=original):
                if not node[2] and node[1].isupper():
                    _calls.append(node[1])
                _original(frame, node, done)

            machine._step_call = traced  # noqa: SLF001
            state = WrittenState(machine.snapshot())
            steps = 0
            while not machine.halted:
                machine.step()
                steps += 1
                state.sample(machine.snapshot())
                assert len(machine.frames) <= 4 * n + 3
                assert sum(len(frame.work) for frame in machine.frames) <= 6 * n + 5
                assert len(machine._serials) <= 2 * len(source) + 2  # noqa: SLF001
            assert read_answer(NAME, machine.io.getvalue()) == expected
            assert len(calls) == len(set(calls))
            assert len(calls) <= 3 * n + 1
            assert steps <= execution(n, source)
            assert state.bits <= workspace(n, source)
            positive += bool(calls)
    if n == 3:
        assert positive > 0


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6])
def test_public_parity_includes_shared_frame_overhead(n):
    from tests.proofs.test_execution_formulas import _measure

    table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
    source = esolangs.generate(NAME, table)
    assert source.count("=") > 1
    steps, bits = _measure(NAME, table, written=True, program=source)
    assert steps <= execution(n, source)
    assert bits <= workspace(n, source)
