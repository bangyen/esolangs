"""Runtime and compiler capabilities for Line."""

from esolangs.languages.line.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
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
            "esolangs.languages.line.generator", "line_request"
        ),
        layout_width=False,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.line.generator", "line_balance_request"
        ),
        no_wrap="tree geometry fixes the width; balance chooses orientation",
    )


LANGUAGE = LanguageDeclaration(
    "Line",
    RuntimeSpec(
        "line",
        source_policy=RasterSourcePolicy(),
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        empty_program="image contains no ink",
    ),
    backend=DeferredBackend(_backend),
)
