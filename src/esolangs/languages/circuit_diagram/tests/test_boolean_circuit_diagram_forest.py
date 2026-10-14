"""Native shared suffix roots, including held internal roots and constants."""

import pytest

from esolangs.languages.circuit_diagram.generator import _circuit_diagram_model
from esolangs.languages.circuit_diagram.generator.banks import (
    _assemble_banks,
    _class_bank_layout,
    _residual_class_bank_candidate,
)
from esolangs.languages.circuit_diagram.generator.forest import _suffix_forest
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
)
from tests.support.witness_tables import dense

from .test_boolean_circuit_diagram_classes import (
    _eight_classes,
    _three_classes,
)


@pytest.mark.medium
@pytest.mark.parametrize("start", [1, 9])
def test_every_nonzero_two_input_function_through_shared_roots(start) -> None:
    words = [f"{value:04b}" for value in range(start, min(start + 8, 16))]
    choices = [row % len(words) for row in range(16)]
    table = "".join(words[choice] for choice in choices)
    parts = [
        [
            (
                _circuit_diagram_model(
                    "".join("1" if choice == index else "0" for choice in choices), None
                ),
                list(range(4)),
            )
        ]
        for index in range(len(words))
    ]
    model = _assemble_banks(
        parts,
        6,
        4,
        shared_suffix=_suffix_forest(words, 2),
    )
    _execute(table, model.render())


@pytest.mark.medium
def test_exported_internal_root_survives_later_consumers() -> None:
    atom = "".join(str((row & 7).bit_count() % 2) for row in range(128))
    parent = "".join(str(int(bit) ^ (row >> 6)) for row, bit in enumerate(atom))
    table = atom + parent + atom + "1" * 128
    model = _class_bank_layout(table, shared=True)
    assert model is not None
    _execute(table, model.render())


@pytest.mark.medium
def test_shared_forest_reduces_distinct_root_gate_count_and_area() -> None:
    table = _eight_classes(13)
    separate = _class_bank_layout(table, shared=False)
    shared = _class_bank_layout(table, shared=True)
    assert separate is not None
    assert shared is not None
    old_height, old_width = separate.bounds()
    height, width = shared.bounds()
    assert height * width == 1_160_811 < old_height * old_width
    assert sum(char in "ao~xX" for char in shared.glyphs.values()) == 874
    assert sum(char in "ao~xX" for char in separate.glyphs.values()) == 1064
    rows = sorted({0, len(table) - 1, *range(0, len(table), len(table) // 32)})
    _execute(table, shared.render(), rows)
    _execute(table, separate.render(), rows)


@pytest.mark.medium
def test_forests_keep_one_maskless_root_and_original_ports() -> None:
    table = dense(7) * 4
    model = _class_bank_layout(table, shared=True)
    assert model is not None
    _execute(table, model.render())


@pytest.mark.medium
def test_larger_projection_forest_keeps_the_separate_body() -> None:
    table = ("0" * 64 + "1" * 64) * 4
    separate = _class_bank_layout(table, shared=False)
    shared = _class_bank_layout(table, shared=True)
    assert separate is not None
    assert shared is not None
    old_height, old_width = separate.bounds()
    height, width = shared.bounds()
    assert height * width > old_height * old_width
    assert _residual_class_bank_candidate(table).render() == separate.render()
    assert (
        _residual_class_bank_candidate(table, old_height * old_width).render()
        == separate.render()
    )
    _execute(table, separate.render())
    _execute(table, shared.render())


@pytest.mark.parametrize(
    ("words", "inputs"),
    [
        ([], 7),
        (["01"] * 9, 1),
        (["01"], 0),
        (["01"], 9),
        (["01"], 2),
        (["0000"], 2),
        (["1111"], 2),
    ],
)
def test_unsupported_forest_domain_aborts(words, inputs) -> None:
    with pytest.raises(ValueError, match="suffix"):
        _suffix_forest(words, inputs)


@pytest.mark.slow
@pytest.mark.parametrize("arities", [(9, 11, 13), (10, 12, 14)])
def test_shared_forest_growth_executes_both_parities(arities) -> None:
    sizes = []
    for n in arities:
        table = _three_classes(n)
        model = _class_bank_layout(table, shared=True)
        assert model is not None
        code = model.render()
        rows = sorted({0, len(table) - 1, *range(0, len(table), len(table) // 32)})
        _execute(table, code, rows)
        sizes.append(len(code))
    assert (sizes[2] - sizes[1]) / (sizes[1] - sizes[0]) <= 4.4
