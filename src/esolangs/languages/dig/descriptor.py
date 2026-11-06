"""Runtime and compiler capabilities for Dig."""

from esolangs.languages.dig.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Dig",
    RuntimeSpec(
        "dig",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        split=True,
        empty_program="Dig program cannot be empty",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.dig.generator", "dig", ("truth_table", "width", "share")
        ),
        balance=FunctionRef(
            "esolangs.languages.dig.generator", "_balance", ("table", "default")
        ),
        grid=True,
    ),
)
