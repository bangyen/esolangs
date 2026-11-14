"""Runtime and compiler capabilities for NOR machine."""

from esolangs.languages.nor_machine.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.nor_machine.generator", "nor_machine_request"
        ),
        layout_width=False,
        # Not a tree: Horner's rule packs every row of the essential-input table.
        shape=Shape.LOOKUP,
        wrap=wrap_chars,
    )


LANGUAGE = LanguageDeclaration(
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
    backend=DeferredBackend(_backend),
)
