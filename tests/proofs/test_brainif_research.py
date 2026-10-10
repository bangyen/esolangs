"""Executed controls for BrainIf's research track: residual DAG and selection."""

import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.tape_based.brainif import _Machine as BrainIf
from esolangs.tools.brainif import (
    _brainif_dag,
    _brainif_tree,
    _residual_layers,
    brainif,
)


def test_residual_dag_worst_case_width_and_size() -> None:
    for n in range(4, 17):
        r = 0
        while 2 ** (r + 1) + r + 1 <= n:
            r += 1
        width = 2 ** (r + 1)
        table = "".join(format(i, f"0{width}b") for i in range(2**n // width))
        layers = _residual_layers(table)
        assert len(layers[r]) == 2**n // width
        assert 2**n / (2 * n) <= len(layers[r])
        assert sum(map(len, layers)) <= 12 * 2**n / n


@pytest.mark.medium
def test_brainif_selection_size_and_steps_never_regress() -> None:
    rng = random.Random(20261002)
    old_total = new_total = old_steps = new_steps = 0
    for n in range(1, 7):
        tables = (
            [format(i, f"0{1 << n}b") for i in range(1 << (1 << n))]
            if n <= 3
            else [
                "0" * (1 << n),
                "1" * (1 << n),
                "".join(str(i.bit_count() % 2) for i in range(1 << n)),
                *("".join(rng.choice("01") for _ in range(1 << n)) for _ in range(4)),
            ]
        )
        for table in tables:
            old, new = _brainif_tree(table, None), brainif(table)
            assert len(new) <= len(old)
            counts = []
            for code in (old, new):
                total = 0
                for row in range(1 << n):
                    io = ScriptedIO("".join(format(row, f"0{n}b")))
                    machine = BrainIf(code.splitlines(), io)
                    count = 0
                    while not machine.halted:
                        machine.step()
                        count += 1
                        assert count <= 10000
                    assert io.getvalue() == table[row]
                    assert io.reads == n
                    total += count
                counts.append(total)
            assert counts[1] <= counts[0]
            if n == 3:
                old_total += len(old)
                new_total += len(new)
                old_steps += counts[0]
                new_steps += counts[1]
    assert (old_total, new_total) == (319576, 291524)
    assert (old_steps, new_steps) == (134984, 74440)


@pytest.mark.medium
def test_dag_forgets_the_previous_input_before_reuse() -> None:
    code = _brainif_dag("00011011").splitlines()
    for row in range(8):
        io = ScriptedIO("".join(format(row, "03b")))
        machine = BrainIf(code, io)
        boundaries = []
        steps = 0
        while not machine.halted:
            if code[machine.ip] == "if 49 input":
                boundaries.append((machine.ptr, machine.tape))
            machine.step()
            steps += 1
        assert boundaries == [(0, (49,)), (0, (49,))]
        assert steps <= 4 * 3 + 50
