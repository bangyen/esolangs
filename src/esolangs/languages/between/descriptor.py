"""Runtime and compiler capabilities for Between."""

from esolangs.languages.between.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Between",
    RuntimeSpec(
        "between",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.between.generator", "between", ("truth_table",)
        ),
        no_wrap="each line is one instruction and a break splits it",
    ),
)
