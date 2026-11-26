"""Runtime and Boolean lookup capabilities for standalone Onecode."""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape, SourceLayout
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.onecode_fergusq.generator", "onecode_fergusq_request"
        ),
        shape=Shape.REDUCING,
        layout=SourceLayout(
            no_wrap="a lookup string must stay on one line",
        ),
    )


LANGUAGE = LanguageDeclaration(
    "Onecode (Fergusq)",
    RuntimeSpec(
        "onecode_fergusq",
        category="variable_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=MachineCapabilities(
            debug=DebugSpec(
                ip="ip",
                ip_shape="opaque",
                memory="_debug_memory",
                memory_at="memory_at",
                views=("origin",),
                stack="stack",
            )
        ),
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(input_shape="char_stream"),
)
