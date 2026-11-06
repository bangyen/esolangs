"""Runtime and compiler capabilities for Forbin."""

from esolangs.languages.forbin.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Forbin",
    RuntimeSpec(
        "forbin",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="variable_based",
        empty_program="Forbin program has no main function",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.forbin.generator", "forbin", ("truth_table", "width")
        ),
        # Not a tree: one painted call argument per entry, halved down to the first.
        shape=Shape.LOOKUP,
        balance=FunctionRef(
            "esolangs.languages.forbin.generator", "_balance", ("table", "default")
        ),
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
