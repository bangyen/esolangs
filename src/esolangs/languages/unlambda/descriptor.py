"""Runtime and compiler capabilities for Unlambda."""

from esolangs.languages.unlambda.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import _unlambda
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.unlambda.generator", "unlambda_request"
        ),
        layout_width=False,
        wrap=_unlambda,
    )


LANGUAGE = LanguageDeclaration(
    "Unlambda",
    RuntimeSpec(
        "unlambda",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        eof="an exhausted '@' hands its argument v, the spec's branch",
        empty_program="an Unlambda program cannot be empty",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
