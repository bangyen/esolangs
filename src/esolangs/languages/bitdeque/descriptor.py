"""Runtime and compiler capabilities for Bitdeque."""

from esolangs.languages.bitdeque.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.registry._backend import (
        BooleanBackend,
        ConstructedLayout,
        TemplateSpec,
    )
    from esolangs.registry._functions import FunctionRef
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.bitdeque.generator", "bitdeque_request"
        ),
        layout=ConstructedLayout(
            same_layout=FunctionRef(
                "esolangs.generation.helpers",
                "same_token_layout",
                ("template", "plain", "_layout"),
            ),
            wrap=FunctionRef(
                "esolangs.languages.bitdeque.generator",
                "_bitdeque",
                ("program", "width"),
            ),
            balance=OperationRef[BalanceRequest, TemplateLayout](
                "esolangs.languages.bitdeque.generator", "bitdeque_balance_request"
            ),
        ),
        # Space-delimited, but ``GOTO`` and its target must stay on one line.
        template=TemplateSpec(
            setters=FunctionRef(
                "esolangs.languages.bitdeque.generator",
                "bitdeque_setters",
                ("template", "n"),
            )
        ),
    )


LANGUAGE = LanguageDeclaration(
    "Bitdeque",
    RuntimeSpec(
        "bitdeque",
        reads_stdin=False,
        category="queue_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        answer_mode="dump",
        note="Bitdeque has no output instruction and dumps its deque at "
        "halt; the generator leaves exactly one bit on it, so the "
        "whole dump is the answer and there is no position to name",
    ),
)
