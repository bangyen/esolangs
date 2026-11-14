"""Runtime and compiler capabilities for Inject."""

from esolangs.languages.inject.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.inject.generator", "inject_request"
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.inject.generator", "inject_balance_request"
        ),
        no_wrap="blocks and executable commands are delimited by source lines",
    )


LANGUAGE = LanguageDeclaration(
    "Inject",
    RuntimeSpec(
        "inject",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="program_based",
        # The wiki cat's only clean exit is a ``readto`` that gets no line.
        eof="an exhausted readto empties the block",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        note="send terminates each line, so the answer ends in a newline",
    ),
    # ``send`` terminates every line it writes, so the answer arrives
    # with a newline after it -- there is no other output command.
    example=Example(expected="0\n"),
)
