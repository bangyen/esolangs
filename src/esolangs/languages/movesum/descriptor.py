"""Runtime and compiler capabilities for Movesum."""

from esolangs.languages.movesum.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.movesum.generator", "movesum_request"
        ),
        layout_width=False,
        # Not a tree: one rung per row, whatever the table says.
        shape=Shape.LOOKUP,
        no_wrap="each line is one instruction and a break splits it",
    )


LANGUAGE = LanguageDeclaration(
    "Movesum",
    RuntimeSpec(
        "movesum",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="tape_based",
        eof="a read at EOF is 0",
        empty_program="Movesum program is empty",
    ),
    backend=DeferredBackend(_backend),
    example=Example(expected="0 0"),
)
