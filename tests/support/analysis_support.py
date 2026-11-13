"""Executed fault controls for declared canonical generator analyses."""

import importlib
from unittest.mock import patch

import esolangs
from esolangs.generation.algebraic import affine_form, parity_bias
from esolangs.generation.anf import anf_coefficients
from esolangs.generation.branch_decoder import hoisted_tree
from esolangs.generation.decision import (
    complemented_diagram,
    decision_layers,
    reduced_diagram,
)
from esolangs.generation.helpers import (
    SubtreeDiagram,
    input_weights,
    read_at,
    subtree_ids,
    symmetric_weights,
)
from esolangs.generation.lookup import prefix_counts
from esolangs.generation.packed_decoder import packed_decoder
from esolangs.generation.shared_flag import flag_tree_body
from esolangs.registry import LANGUAGES
from esolangs.registry._operations import OperationRef
from tests.support.generator_support import evaluate_generated


def assert_analysis_complement(
    name: str,
    attribute: str,
    table: str = "0011",
    *,
    rows: tuple[int, ...] | None = None,
    width: int | None = None,
) -> None:
    """Require an injected analysis fault to complement every actual answer."""
    backend = LANGUAGES[name].backend
    assert backend is not None
    reference = backend.entrypoint
    assert isinstance(reference, OperationRef)
    module = importlib.import_module(reference.module)
    owner, _, attribute = attribute.rpartition(".")
    module = getattr(module, owner) if owner else module
    query = {
        "anf_coefficients": anf_coefficients,
        "complemented_diagram": complemented_diagram,
        "SubtreeDiagram": SubtreeDiagram,
        "hoisted_tree": hoisted_tree,
        "_sbleq_hoisted": hoisted_tree,
        "packed_decoder": packed_decoder,
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
        expected = table.translate(str.maketrans("01", "10"))
        if rows is None:
            assert evaluate_generated(name, table, width=width) == expected
        else:
            program = esolangs.generate(name, table, width=width)
            n = len(table).bit_length() - 1
            for row in rows:
                bits = [(row >> shift) & 1 for shift in range(n - 1, -1, -1)]
                assert isinstance(program, esolangs.ProgramArtifact)
                stdin = esolangs.encode_inputs(name, bits, truth_table=table)
                result = esolangs.run(
                    name,
                    program,
                    stdin=stdin,
                    limits=esolangs.ExecutionLimits(max_steps=100000),
                )
                assert esolangs.read_answer(name, result.output) == expected[row]
                assert result.input_position == len(stdin)
                assert result.input_past_end == 0
        assert corrupted.called
