"""Runtime and compiler capabilities for CreativeScript v2."""

from esolangs.languages.creativescript_v2.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
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
            "esolangs.languages.creativescript_v2.generator",
            "creativescript_v2_request",
        ),
        layout_width=False,
        no_wrap="a break changes the line a command ends on",
        # No jump: the table is data, indexed by arithmetic, not a tree.
        shape=Shape.LOOKUP,
    )


LANGUAGE = LanguageDeclaration(
    "CreativeScript v2",
    RuntimeSpec(
        "creativescript_v2",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
        empty_program="a CreativeScript v2 program needs at least one command",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(),
)
