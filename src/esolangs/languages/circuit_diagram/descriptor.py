"""Runtime and compiler capabilities for Circuit Diagram."""

from esolangs.languages.circuit_diagram.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
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
            "esolangs.languages.circuit_diagram.generator", "circuit_diagram_request"
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.circuit_diagram.generator",
            "circuit_diagram_balance_request",
        ),
        grid=True,
    )


LANGUAGE = LanguageDeclaration(
    "Circuit Diagram",
    RuntimeSpec(
        "circuit_diagram",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        source_policy=LineSourcePolicy(),
        eof="resolves its inputs while laying the grid",
    ),
    example=Example(slow_build=True),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
        ignores_whitespace=True,
    ),
)
