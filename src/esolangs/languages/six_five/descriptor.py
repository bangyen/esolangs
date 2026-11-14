"""Runtime and compiler capabilities for 6-5."""

from esolangs.languages.six_five.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import _six_five
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.six_five.generator", "six_five_request"
        ),
        layout_width=False,
        # 7n/8n are two-character tokens; see ``_SIX_FIVE_COMMAND``.
        wrap=_six_five,
    )


LANGUAGE = LanguageDeclaration(
    "6-5",
    RuntimeSpec(
        "six_five",
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
