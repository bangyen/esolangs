"""Runtime and compiler capabilities for Container."""

from esolangs.languages.container.lifecycle import CAPABILITIES
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
            "esolangs.languages.container.generator", "container_request"
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.container.generator", "container_balance_request"
        ),
        no_wrap="each line declares a container or one of its rules",
    )


LANGUAGE = LanguageDeclaration(
    "Container",
    RuntimeSpec(
        "container",
        category="variable_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        source_policy=LineSourcePolicy(),
        # Wiki: the empty container sets IN "with EOF returning 0".
        eof="an exhausted read sets IN to the spec's 0",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        note="Container prints the answer; module.run returns the EXIT code.",
        input_shape="char_stream",
    ),
)
