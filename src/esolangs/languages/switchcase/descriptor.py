"""Runtime and compiler capabilities for SwitchCase."""

from esolangs.languages.switchcase.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "SwitchCase",
    RuntimeSpec(
        "switchcase",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="variable_based",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.switchcase.generator", "switchcase", ("truth_table",)
        ),
        shape=Shape.TREE,
        no_wrap="a line is one arm, and a case's arms follow its $ line",
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
