"""Runtime and compiler capabilities for Painfuck."""

from esolangs.generation.wrap import wrap_chars
from esolangs.languages.painfuck.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Painfuck",
    RuntimeSpec(
        "painfuck",
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.painfuck.generator", "painfuck", ("truth_table",)
        ),
        wrap=wrap_chars,
    ),
)
