"""Runtime and compiler capabilities for Rubic."""

from esolangs.generation.wrap import wrap_space_delimited
from esolangs.languages.rubic.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Rubic",
    RuntimeSpec(
        "rubic",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.rubic.generator", "rubic", ("truth_table",)
        ),
        wrap=wrap_space_delimited,
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
