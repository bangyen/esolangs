"""Runtime and compiler capabilities for BrainIf."""

from esolangs.languages.brainif.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import LineSourcePolicy, RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, ConstructedLayout
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.brainif.generator", "brainif_request"
        ),
        layout=ConstructedLayout(
            layout_balance=True,
            no_wrap="each line is one instruction and goto targets are line numbers",
        ),
        # The default DAG wins the balance race (full and zero-jump trees,
        # n=1..8), so the generator uses the same path for both.
    )


LANGUAGE = LanguageDeclaration(
    "BrainIf",
    RuntimeSpec(
        "brainif",
        category="tape_based",
        source_policy=LineSourcePolicy(),
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
