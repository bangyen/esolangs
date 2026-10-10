"""Mixed-level ternary dispatch, exact prices, and resource admission."""

import random

import pytest

from esolangs.debugger import make_vm
from esolangs.tools.sstack import _sstack_tree, sstack
from esolangs.tools.sstack_binary import _Metric
from esolangs.tools.sstack_ternary import _PROLOGUE, _decoder, _width, best_ternary_bank
from scripts.benchmark import WrittenState


@pytest.mark.parametrize("classes", range(2, 29))
def test_decoder_consumes_every_word_before_its_body(classes):
    width = _width(classes)
    pieces = []
    chars, tails = _decoder(
        width, tuple(_Metric(3, 1) for _ in range(classes)), pieces.append
    )
    decoder = "".join(":b:" if isinstance(piece, int) else piece for piece in pieces)
    assert len(decoder) == chars
    for label in range(classes):
        word = "".join(f'"{1 + label // 3**bit % 3}/e"' for bit in range(width))
        vm = make_vm("SStack", _PROLOGUE + word + decoder, stdin="")
        count = 0
        while not vm.halted and count < 100:
            vm.step()
            count += 1
        assert vm.halted
        assert vm.output == "1"
        assert count == 5 + width + tails[label]
    vm = make_vm("SStack", _PROLOGUE + decoder, stdin="")
    while not vm.halted:
        vm.step()
    assert vm.output == ""


def _mixed_table():
    rng = random.Random(15)
    words = []
    while len(words) < 128:
        word = "".join(rng.choice("01") for _ in range(16))
        if word not in words:
            words.append(word)
    chunks = [words[2 * i] + words[2 * i + 1] for i in range(48)] * 2
    single = words[96:] * 2
    rng.shuffle(single)
    chunks += [single[i] + single[i + 1] for i in range(0, 64, 2)]
    rng.shuffle(chunks)
    return "".join(chunks) * 16


def test_mixed_bank_exceeds_numeric_capacity_and_passes_admission():
    table = _mixed_table()
    result = best_ternary_bank(table, _sstack_tree, 115, 39492)
    assert result is not None
    program, commands = result
    assert len(program) == 38713
    assert commands == 110
    assert sstack(table) == program
    bound = 6 * 16 + 12 + (16).bit_length() + len(program).bit_length()
    for row in (0, 1, 127, 255, 1023, 2047, 4095, 65535):
        vm = make_vm("SStack", program, stdin=f"{row:016b}" + "B")
        written = WrittenState(vm.snapshot())
        count = 0
        while not vm.halted and count <= commands:
            vm.step()
            written.sample(vm.snapshot())
            count += 1
        assert vm.halted
        assert vm.output == table[row]
        assert count <= commands
        assert written.bits <= bound
    assert best_ternary_bank(table, _sstack_tree, commands - 1, 39492) is None
    assert best_ternary_bank(table, _sstack_tree, 115, len(program)) is None


@pytest.mark.parametrize("table", ["00", "01", "0011", "01101001", "0" * 64])
def test_bank_refuses_without_multiple_eligible_reachable_definitions(table):
    assert best_ternary_bank(table, _sstack_tree, 1000, 100000) is None


@pytest.mark.parametrize("seed", range(5))
def test_admitted_small_banks_execute_every_row(seed):
    rng = random.Random(seed)
    a, b, c = ("".join(rng.choice("01") for _ in range(32)) for _ in range(3))
    table = "0" * 32 + a + b + a + "1" * 32 + b + c + c
    result = best_ternary_bank(table, _sstack_tree, 1000, 100000)
    assert result is not None
    program, commands = result
    peak = 0
    for row, expected in enumerate(table):
        vm = make_vm("SStack", program, stdin=f"{row:08b}")
        count = 0
        while not vm.halted and count <= commands:
            vm.step()
            count += 1
        assert vm.halted
        assert vm.output == expected
        peak = max(peak, count)
    assert peak == commands


def test_render_price_disagreement_aborts():
    table = _mixed_table()

    def wrong_body(block):
        program, commands = _sstack_tree(block)
        return program + ";d;", commands + 1

    with pytest.raises(ValueError, match="disagrees with its price"):
        best_ternary_bank(table, wrong_body, 115, 39492)
