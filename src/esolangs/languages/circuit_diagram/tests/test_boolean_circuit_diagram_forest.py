"""Native shared suffix roots, including held internal roots and constants."""

import pytest

from esolangs.languages.circuit_diagram.generator import _circuit_diagram_model
from esolangs.languages.circuit_diagram.generator.banks import (
    _assemble_banks,
)
from esolangs.languages.circuit_diagram.generator.forest import _suffix_forest
from esolangs.languages.circuit_diagram.tests.test_boolean_circuit_diagram_pool import (
    _execute,
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
