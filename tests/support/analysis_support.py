"""Executed fault controls for declared canonical generator analyses."""

import importlib
from unittest.mock import patch

from esolangs.generation.algebraic import affine_form, parity_bias
from esolangs.generation.decision import decision_layers, reduced_diagram
from esolangs.generation.helpers import (
    SubtreeDiagram,
    input_weights,
    read_at,
    subtree_ids,
    symmetric_weights,
)
from esolangs.generation.lookup import prefix_counts
from esolangs.generation.shared_flag import flag_tree_body
from esolangs.registry import LANGUAGES
from esolangs.registry._functions import FunctionRef
from tests.support.generator_support import evaluate_generated


def assert_analysis_complement(name: str, attribute: str, table: str = "0011") -> None:
    """Require an injected analysis fault to complement every actual answer."""
    backend = LANGUAGES[name].backend
    assert backend is not None
    reference = backend.entrypoint
    assert isinstance(reference, FunctionRef)
    module = importlib.import_module(reference.module)
    query = {
        "SubtreeDiagram": SubtreeDiagram,
        "affine_form": affine_form,
        "parity_bias": parity_bias,
        "decision_layers": decision_layers,
        "reduced_diagram": reduced_diagram,
        "subtree_ids": subtree_ids,
        "prefix_counts": prefix_counts,
        "read_at": read_at,
        "input_weights": input_weights,
        "symmetric_weights": symmetric_weights,
        "flag_tree_body": flag_tree_body,
    }[attribute]
    assert getattr(module, attribute) is query
    with patch.object(
        module,
        attribute,
        side_effect=lambda table, *args, **kwargs: query(
            table.translate(str.maketrans("01", "10")), *args, **kwargs
        ),
    ) as corrupted:
        assert evaluate_generated(name, table) == table.translate(
            str.maketrans("01", "10")
        )
        assert corrupted.called
