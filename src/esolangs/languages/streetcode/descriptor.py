"""Runtime and compiler capabilities for Streetcode."""

from esolangs.languages.streetcode.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
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
            "esolangs.languages.streetcode.generator", "streetcode_request"
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.streetcode.generator", "streetcode_balance_request"
        ),
        grid=True,
    )


LANGUAGE = LanguageDeclaration(
    "Streetcode",
    RuntimeSpec(
        "streetcode",
        completion_entrypoint="_execute_program",
        machine_preparation="prepare_machine",
        capabilities=CAPABILITIES,
        category="grid_based",
        source_policy=LineSourcePolicy(),
        empty_program="Streetcode program cannot be empty",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
