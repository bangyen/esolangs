"""Runtime and compiler capabilities for Modulous."""

from esolangs.languages.modulous.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.modulous.generator", "modulous_request"
        ),
        layout_width=True,
        # Not a tree: pops a ``PSH STR`` table down to the indexed character.
        shape=Shape.LOOKUP,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.modulous.generator", "modulous_balance_request"
        ),
    )


LANGUAGE = LanguageDeclaration(
    "Modulous",
    RuntimeSpec(
        "modulous",
        category="stack_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
    ),
    backend=DeferredBackend(_backend),
)
