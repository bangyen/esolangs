"""Runtime and compiler capabilities for BFStack."""

from esolangs.languages.bfstack.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend, Shape, SourceLayout
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.bfstack.generator", "bfstack_request"
        ),
        layout=SourceLayout(
            wrap=wrap_chars,
        ),
        # A sum, not a tree: a lookup over the essential inputs only.
        shape=Shape.REDUCING,
    )


LANGUAGE = LanguageDeclaration(
    "BFStack",
    RuntimeSpec(
        "bfstack",
        category="stack_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
