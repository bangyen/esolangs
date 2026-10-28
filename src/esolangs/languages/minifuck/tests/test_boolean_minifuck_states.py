"""Two-state residuals use guarded setters, including non-affine updates."""

import itertools
import random

import pytest

import esolangs
from esolangs.generation.helpers import TEMPLATE_CHAR, fill_runs
from esolangs.languages.minifuck.generator import _affine_mask, minifuck_setters
from esolangs.languages.minifuck.generator.states import _emit, two_state
from esolangs.languages.minifuck.interpreter import _Machine
from esolangs.runtime.io import ScriptedIO


@pytest.mark.medium
def test_every_small_two_state_table_runs() -> None:
    served = nonlinear = 0
    for n in range(1, 4):
        for values in itertools.product("01", repeat=1 << n):
            table = "".join(values)
            template = two_state(table)
            if template is None:
                continue
            served += 1
            nonlinear += _affine_mask(table) is None
            for row, expected in enumerate(table):
                bits = [row >> shift & 1 for shift in range(n - 1, -1, -1)]
                source = fill_runs(
                    template, TEMPLATE_CHAR, minifuck_setters(template, n), bits
                )
                assert esolangs.run("Minifuck", source) == expected
    # A minority at input 1 is read through "[<[x<", so one setter pair serves
    # every orientation, mixed chains included.
    assert (served, nonlinear) == (108, 80)
    assert two_state("0" * 15 + "1") is not None  # AND: mixed 0,1,1,...,1


@pytest.mark.medium
@pytest.mark.parametrize("junk", [0, 1, 2, 7])
def test_every_update_ignores_scratch_bits(junk) -> None:
    for values in itertools.product((0, 1), repeat=4):
        template = _emit([[0, 1, 0, 1], list(values)], 0)
        for row, expected in enumerate(values):
            source = fill_runs(
                template,
                TEMPLATE_CHAR,
                minifuck_setters(template, 2),
                [row >> 1, row & 1],
            )
            machine = _Machine(source, ScriptedIO(""))
            machine.state = (source, junk << 8, 11, 0, 0)
            while not machine.halted:
                machine.step()
            assert machine.io.getvalue() == str(expected)
            assert machine.state[3] <= 10


@pytest.mark.medium
@pytest.mark.parametrize("seed", [79, 93, 168, 196])
def test_public_nonlinear_state_layouts_run_every_eight_input_row(seed) -> None:
    n = 8
    rng = random.Random(612026 + seed)
    gates = [tuple(rng.randrange(2) for _ in range(3)) for _ in range(n - 1)]
    table = []
    for row in range(1 << n):
        bits = [row >> shift & 1 for shift in range(n - 1, -1, -1)]
        state = bits[0]
        for bit, (left, right, output) in zip(bits[1:], gates, strict=True):
            state = ((state ^ left) & (bit ^ right)) ^ output
        table.append(str(state))
    truth_table = "".join(table)
    assert _affine_mask(truth_table) is None
    for width, balance in ((None, False), (1, False), (4, False), (None, True)):
        template = esolangs.generate(
            "Minifuck", truth_table, width=width, balance=balance
        )
        for row, expected in enumerate(truth_table):
            bits = [row >> shift & 1 for shift in range(n - 1, -1, -1)]
            source = esolangs.instantiate("Minifuck", str(template), bits)
            assert esolangs.run("Minifuck", source) == expected


def test_three_residuals_are_refused() -> None:
    assert two_state("00010111") is None
