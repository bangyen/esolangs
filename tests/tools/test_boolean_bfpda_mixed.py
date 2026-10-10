"""Mixed-depth BF-PDA words and protected completed-output paths."""

import random

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.interpreters.stack_based.bf_pda import _Machine
from esolangs.tools.bfpda import _prepare, _reflected, bfpda
from esolangs.tools.bfpda_bank import _Metric
from esolangs.tools.bfpda_mixed import _decoder, best_mixed_bank
from tests.tools.fills import fill
from tests.tools.test_boolean_bfpda import _execute_bank

_fill_bfpda = fill("BF-PDA")


@pytest.mark.parametrize("classes", range(2, 20))
def test_decoder_consumes_each_bit_marker_pair(classes):
    width = (classes - 1).bit_length()
    pieces = []
    size, tails = _decoder(
        width, tuple(_Metric(1, 1) for _ in range(classes)), pieces.append
    )
    decoder = "".join("." if isinstance(piece, int) else piece for piece in pieces)
    assert len(decoder) == size
    for label in range(classes):
        word = "".join(
            "<@<" + ("@" if label & (1 << bit) else "") for bit in range(width)
        )
        vm = _Machine(word + decoder, ScriptedIO(""))
        count = 0
        while not vm.halted and count < 200:
            vm.step()
            count += 1
        assert vm.halted
        assert vm.io.getvalue() == "0"
        assert count == len(word) + tails[label]
        assert not vm.stack


def _fixture(seed=15, n=16):
    rng = random.Random(seed)
    a, b, c = ("".join(rng.choice("01") for _ in range(k)) for k in (32, 16, 16))
    core = a + b + c + a + c + b
    return _reflected(core * (1 << (n - 7)), n)


def test_public_mixed_bank_shares_two_levels_within_bounds():
    table = _fixture()
    context = _prepare(table)
    program = best_mixed_bank(context, 162, 606)
    assert program is not None
    assert len(program) == 583
    assert bfpda(table) == program
    rows = [
        int(f"{fill:09b}{row:07b}"[::-1], 2) for fill in (0, 511) for row in range(128)
    ]
    assert _execute_bank(table, program, rows) == 157
    assert best_mixed_bank(context, 156, 606) is None
    assert best_mixed_bank(context, 162, len(program)) is None


@pytest.mark.parametrize("seed", range(5))
def test_varied_mixed_bodies_execute_all_essential_rows(seed):
    table = _fixture(seed, 16)
    program = best_mixed_bank(_prepare(table), 162, 100000)
    assert program is not None
    rows = [
        int(f"{fill:09b}{row:07b}"[::-1], 2) for fill in (0, 511) for row in range(128)
    ]
    _execute_bank(table, program, rows)


@pytest.mark.parametrize("table", ["00", "01", "0011", "01101001", "0" * 64])
def test_bank_refuses_without_multiple_retired_space_eligible_states(table):
    assert best_mixed_bank(_prepare(table), 162, 100000) is None


def test_completed_constant_prefix_paths_do_not_enter_decoder():
    rng = random.Random(15)
    a, b = ("".join(rng.choice("01") for _ in range(16)) for _ in range(2))
    core = "0" * 16 + a + b + a + "1" * 16 + b + "0" * 32
    table = _reflected(core * 512, 16)
    program = best_mixed_bank(_prepare(table), 162, 100000)
    assert program is not None
    rows = [
        int(f"{fill:09b}{row:07b}"[::-1], 2) for fill in (0, 511) for row in range(128)
    ]
    _execute_bank(table, program, rows)
    for row in rows:
        machine = _Machine(
            _fill_bfpda(program, [int(c) for c in f"{row:016b}"]), ScriptedIO("")
        )
        while not machine.halted:
            machine.step()
            assert len(machine.stack) <= 32


@pytest.mark.parametrize("seed", range(5))
def test_twelve_input_control_is_refused_at_its_command_bound(seed):
    assert best_mixed_bank(_prepare(_fixture(seed, 12)), 122, 100000) is None
