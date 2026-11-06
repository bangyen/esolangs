"""Runtime and compiler capabilities for SStack."""

from esolangs.generation.wrap import wrap_chars
from esolangs.languages.sstack.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "SStack",
    RuntimeSpec(
        "sstack",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.sstack.generator", "sstack", ("truth_table",)
        ),
        # Whitespace is discarded anywhere, inside a token too.
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
