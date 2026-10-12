"""Shared expressions preserve ordered paths and evaluator resource bounds."""

import random

import pytest

import esolangs
from esolangs.languages.algebraic_programming_language.generator import (
    _apl_reduced_ordered,
    _apl_repeated_expressions,
    _apl_split,
)
from esolangs.languages.algebraic_programming_language.interpreter import _Machine
from esolangs.languages.algebraic_programming_language.tests.formulas import (
    execution,
    workspace,
)
from esolangs.runtime._answers import read_answer
from esolangs.runtime.io import ScriptedIO
from scripts.benchmark import WrittenState

NAME = "Algebraic Programming Language"


@pytest.mark.medium
@pytest.mark.parametrize("sharing", ["frames", "expressions"])
@pytest.mark.parametrize(
    ("n", "band"), [(1, 0), (2, 0), (3, 0), (3, 1), (3, 2), (3, 3)]
)
def test_shared_expressions_obey_bounds_for_every_small_table(
    n, band, sharing, monkeypatch
) -> None:
    from esolangs.languages.algebraic_programming_language import interpreter as apl

    positive = 0
    calls: list[str] = []
    original = apl._step_call  # noqa: SLF001

    def traced(state, frame, node, done, *, _calls=calls, _original=original):
        if not node[2] and node[1].isupper():
            _calls.append(node[1])
        return _original(state, frame, node, done)

    monkeypatch.setattr(apl, "_step_call", traced)
    span = 64 if n == 3 else 1 << (1 << n)
    for value in range(band * span, (band + 1) * span):
        table = f"{value:0{1 << n}b}"
        perm = tuple(range(n))
        if sharing == "frames":
            source = _apl_split(table, perm, 1, _apl_reduced_ordered)[0]
        else:
            plain = _apl_reduced_ordered(table, perm)
            source = _apl_repeated_expressions(plain)
            assert len(source) <= len(plain)
        for row, expected in enumerate(table):
            bits = [row >> shift & 1 for shift in range(n - 1, -1, -1)]
            machine = _Machine(source, ScriptedIO(esolangs.encode_inputs(NAME, bits)))
            calls.clear()
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
    if n == 3 and (sharing == "frames" or band in (1, 2)):
        assert positive > 0


@pytest.mark.medium
@pytest.mark.parametrize("n", [4, 5, 6])
def test_public_parity_selects_shared_frames(n) -> None:
    table = "".join(str(row.bit_count() & 1) for row in range(1 << n))
    source = esolangs.generate(NAME, table)
    assert source.count("=") > 1


@pytest.mark.medium
@pytest.mark.parametrize("n", [8, 10])
def test_named_groups_keep_large_input_bindings(n) -> None:
    table = format(random.Random(91026 + n).getrandbits(1 << n), f"0{1 << n}b")
    source = _apl_repeated_expressions(_apl_reduced_ordered(table, tuple(range(n))))
    definitions = source.count("=") - 1
    assert definitions > (26 if n == 10 else 0)
    for row in (0, (1 << n) // 2, (1 << n) - 1):
        bits = [int(bit) for bit in format(row, f"0{n}b")]
        actual = esolangs.run(NAME, source, stdin=esolangs.encode_inputs(NAME, bits))
        assert read_answer(NAME, actual) == table[row]
