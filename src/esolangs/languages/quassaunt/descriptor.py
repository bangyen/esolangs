"""Runtime and compiler capabilities for Quassaunt."""

from esolangs.generation.wrap import wrap_space_delimited
from esolangs.languages.quassaunt.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Quassaunt",
    RuntimeSpec(
        "quassaunt",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.quassaunt.generator", "quassaunt", ("truth_table",)
        ),
        # Whitespace separates words and a word holds none, so break only there.
        wrap=wrap_space_delimited,
        balance=FunctionRef(
            "esolangs.languages.quassaunt.generator", "_balance", ("_table", "default")
        ),
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
