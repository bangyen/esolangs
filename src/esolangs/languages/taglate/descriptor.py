"""Runtime and compiler capabilities for Taglate."""

from esolangs.languages.taglate.lifecycle import CAPABILITIES
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
    from esolangs.registry._functions import FunctionRef
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.taglate.generator", "taglate_request"
        ),
        layout_width=True,
        # Both concatenate before tokenizing (Taglate after the queue seed; A
        # Painter Ant drops whitespace), so no break can land inside a command.
        wrap=FunctionRef(
            "esolangs.languages.taglate.wrapping", "_taglate", ("program", "width")
        ),
        wrap_multiline=True,
        same_layout=FunctionRef(
            "esolangs.languages.taglate.wrapping",
            "same_layout",
            ("template", "plain", "_layout"),
        ),
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.taglate.generator", "taglate_balance_request"
        ),
    )


LANGUAGE = LanguageDeclaration(
    "Taglate",
    RuntimeSpec(
        "taglate",
        category="queue_based",
        source_policy=LineSourcePolicy(),
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(input_shape="char_stream"),
)
