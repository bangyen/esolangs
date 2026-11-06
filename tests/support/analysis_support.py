"""Executed fault controls for declared canonical generator analyses."""

import importlib
from unittest.mock import patch

from esolangs.generation.decision import decision_layers, reduced_diagram
from esolangs.generation.helpers import subtree_ids
from esolangs.registry import LANGUAGES
from esolangs.registry._functions import FunctionRef
from tests.support.generator_support import evaluate_generated


def assert_analysis_complement(name: str, attribute: str) -> None:
    """Require an injected analysis fault to complement all four actual answers."""
    backend = LANGUAGES[name].backend
    assert backend is not None
    reference = backend.entrypoint
    assert isinstance(reference, FunctionRef)
    module = importlib.import_module(reference.module)
    query = {
        "decision_layers": decision_layers,
        "reduced_diagram": reduced_diagram,
        "subtree_ids": subtree_ids,
    }[attribute]
    assert getattr(module, attribute) is query
    with patch.object(
        module,
        attribute,
        side_effect=lambda table, *args: query(
            table.translate(str.maketrans("01", "10")), *args
        ),
    ) as corrupted:
        assert evaluate_generated(name, "0011") == "1100"
        assert corrupted.called
