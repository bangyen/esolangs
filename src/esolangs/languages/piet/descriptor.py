"""Runtime and compiler capabilities for Piet."""

from esolangs.languages.piet.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import (
    RasterSourcePolicy,
    RuntimeSpec,
)


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.piet.generator", "piet_request"
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.piet.generator", "piet_balance_request"
        ),
    )


LANGUAGE = LanguageDeclaration(
    "Piet",
    RuntimeSpec(
        "piet",
        source_policy=RasterSourcePolicy(),
        category="stack_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        eof="an exhausted input command is ignored, as the spec requires",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        note="the committed example is drawn at 80 pixels per codel; "
        "generate draws 1 unless --scale says otherwise"
    ),
    example=Example(scale=80),
)
