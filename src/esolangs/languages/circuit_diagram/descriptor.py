"""Runtime and compiler capabilities for Circuit Diagram."""

from esolangs.registry._backend import BooleanBackend
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
