"""Runtime and compiler capabilities for NOR machine."""

from esolangs.generation.wrap import wrap_chars
from esolangs.languages.nor_machine.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "NOR machine",
    RuntimeSpec(
        "nor_machine",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="queue_based",
        eof="every input is enqueued first, so a short input is a shorter queue",
        empty_program="a program with no command loops forever",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.nor_machine.generator", "nor_machine", ("truth_table",)
        ),
        # Not a tree: Horner's rule packs every row of the essential-input table.
        shape=Shape.LOOKUP,
        wrap=wrap_chars,
    ),
)
