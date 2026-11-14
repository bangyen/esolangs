"""Runtime and compiler capabilities for Dig."""

from esolangs.languages.dig.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import LineSourcePolicy, RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.dig.generator", "dig_request"
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.dig.generator", "dig_balance_request"
        ),
        grid=True,
    )


LANGUAGE = LanguageDeclaration(
    "Dig",
    RuntimeSpec(
        "dig",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        source_policy=LineSourcePolicy(),
        empty_program="Dig program cannot be empty",
    ),
    backend=DeferredBackend(_backend),
)
