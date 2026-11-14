"""Runtime and compiler capabilities for ABCDirection."""

from esolangs.languages.abcdirection.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
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
            "esolangs.languages.abcdirection.generator", "abcdirection_request"
        ),
        layout_width=False,
        shape=Shape.REDUCING,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.abcdirection.generator", "abcdirection_balance_request"
        ),
        no_wrap="a newline adds a grid row and moves every vertical path",
        grid=True,
    )


LANGUAGE = LanguageDeclaration(
    "ABCDirection",
    RuntimeSpec(
        "abcdirection",
        category="grid_based",
        eof="EOF supplies zero bits",
        empty_program="program must contain a line with DDDDDD",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(input_shape="char_stream"),
)
