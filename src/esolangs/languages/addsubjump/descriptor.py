"""Runtime and compiler capabilities for AddSubJump."""

from esolangs.generation.wrap import wrap_grid
from esolangs.languages.addsubjump.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "AddSubJump",
    RuntimeSpec(
        "addsubjump",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.addsubjump.generator", "addsubjump", ("truth_table",)
        ),
        wrap=wrap_grid,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
