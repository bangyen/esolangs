"""Executed class sharing admitted by the workspace gate budget."""

import pytest

from esolangs.interpreters.io import ScriptedIO
from esolangs.languages.circuit_diagram.generator import circuit_diagram
from esolangs.languages.circuit_diagram.generator.banks import (
    _class_bank_layout,
    _residual_class_bank_candidate,
)
from esolangs.languages.circuit_diagram.generator.forest import _suffix_forest
from esolangs.languages.circuit_diagram.interpreter import _Machine
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
)
from tests.support.witness_tables import dense


def _sixteen_classes(n):
    tail = 7 if n % 2 else 8
    prefix = n - tail
    atoms = [dense(tail, f"budget-class:{i}".encode()) for i in range(16)]
    masks = [dense(prefix, f"budget-bit:{i}".encode()) for i in range(4)]
    return "".join(
        atoms[sum(int(masks[bit][row]) << bit for bit in range(4))]
        for row in range(1 << prefix)
    )


def test_complete_two_input_basis_has_fourteen_gates_plus_complements():
    words = [f"{value:04b}" for value in range(1, 15)]
    model, endpoints = _suffix_forest(words, 2)
    assert sum(char in "ao~xX" for char in model.glyphs.values()) == 16
    outputs = {point for point, char in model.glyphs.items() if char == ":"}
    for word, endpoint in zip(words, endpoints, strict=True):
        assert endpoint is not None
        chosen = endpoint[0] + 2, endpoint[1]
        for point in outputs:
            model.glyphs[point] = ":" if point == chosen else "-"
        code = model.render().splitlines()
        for row in range(4):
            io = ScriptedIO(f"{row:02b}")
            vm = _Machine(code, io)
            for _ in range(6):
                if vm.halted:
                    break
                vm.step()
            assert vm.halted
            assert io.progress() == 2
            assert io.getvalue() == word[row]


@pytest.mark.medium
def test_sixteen_classes_share_beyond_the_old_cap_and_execute():
    table = _sixteen_classes(13)
    assert len({table[i : i + 128] for i in range(0, len(table), 128)}) == 16
    model = _residual_class_bank_candidate(table)
    assert model is not None
    height, width = model.bounds()
    assert height * width == 2_453_905
    code = circuit_diagram(table)
    assert code == model.render()
    rows = sorted({0, len(table) - 1, *range(0, len(table), 256)})
    _execute(table, code, rows)


@pytest.mark.slow
def test_sixteen_eight_input_roots_keep_the_smaller_separate_layout():
    table = _sixteen_classes(14)
    separate = _class_bank_layout(table, shared=False)
    shared = _class_bank_layout(table, shared=True)
    assert separate is not None
    assert shared is not None
    height, width = separate.bounds()
    old_height, old_width = shared.bounds()
    assert height * width == 4_703_203 < old_height * old_width
    assert sum(char in "ao~xX" for char in shared.glyphs.values()) == 2389
    assert sum(char in "ao~xX" for char in separate.glyphs.values()) == 3362
    rows = sorted({0, len(table) - 1, *range(0, len(table), 512)})
    _execute(table, separate.render(), rows)
    _execute(table, shared.render(), rows)


@pytest.mark.slow
def test_atom_mask_bound_admits_129_classes_across_carry_boundaries():
    atoms = [dense(7, f"too-many:{i}".encode()) for i in range(129)]
    table = "".join(atoms[row % 129] for row in range(256))
    old_gate_bound = 129 * (512 + 8 + 114 + 2) - 1
    assert old_gate_bound > 2 * len(table) + 8 * 15 + 111
    model = _residual_class_bank_candidate(table)
    assert model is not None
    height, width = model.bounds()
    assert height * width == 21_209_025
    rows = sorted(
        {
            0,
            len(table) - 1,
            *range(0, len(table), 1024),
            (127 << 7) + atoms[127].index("1"),
            (128 << 7) + atoms[128].index("1"),
        }
    )
    _execute(table, model.render(), rows)


@pytest.mark.slow
@pytest.mark.parametrize("arities", [(11, 13, 15), (12, 14, 16)])
def test_larger_class_banks_keep_both_parity_growth_bounds(arities):
    sizes = []
    for n in arities:
        table = _sixteen_classes(n)
        model = _residual_class_bank_candidate(table)
        assert model is not None
        height, width = model.bounds()
        sizes.append(height * width)
        rows = sorted({0, len(table) - 1, *range(0, len(table), len(table) // 32)})
        _execute(table, model.render(), rows)
    assert sizes[1] - sizes[0] > 0
    assert 0 < sizes[2] - sizes[1] <= 4.4 * (sizes[1] - sizes[0])
