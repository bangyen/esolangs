"""Runtime and compiler capabilities for FALSE."""

from esolangs.languages.false.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.generation.wrap import _false
    from esolangs.registry._backend import BooleanBackend, ConstructedLayout
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.false.generator", "false_request"
        ),
        layout=ConstructedLayout(
            wrap=_false,
            balance=OperationRef[BalanceRequest, Program](
                "esolangs.languages.false.generator", "false_balance_request"
            ),
        ),
        # ``'x`` and ``.x``/``?x`` take the character after them.
    )


LANGUAGE = LanguageDeclaration(
    "FALSE",
    RuntimeSpec(
        "false",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
        eof="an exhausted '^' is the spec's -1",
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
