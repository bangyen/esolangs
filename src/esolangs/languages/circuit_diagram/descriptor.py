"""Runtime and compiler capabilities for Circuit Diagram."""

from esolangs.registry._backend import BooleanBackend
from esolangs.registry._certification import CertificationSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Circuit Diagram",
    RuntimeSpec(
        "circuit_diagram",
        category="grid_based",
        split=True,
        eof="resolves its inputs while laying the grid",
    ),
    certification=CertificationSpec(
        layout_switch=(7, 8),
        # The H-layout is not asymptotic below n=8, so it has no room for a
        # third rung; the deep contract carries it on a backstop for the same
        # reason, and its area recurrence is checked with the construction
        # invariants.
        scaling_rungs=(8, 9),
        documented_sizes=(52_057, 106_751, 2.05),
    ),
    example=Example(slow_build=True),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.circuit_diagram.generator",
            "circuit_diagram",
            ("truth_table", "width"),
        ),
        balance=FunctionRef(
            "esolangs.languages.circuit_diagram.generator",
            "_balance",
            ("table", "default", "options"),
        ),
        grid=True,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
        ignores_whitespace=True,
    ),
)
