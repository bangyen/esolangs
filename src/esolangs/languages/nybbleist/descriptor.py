"""Runtime and compiler capabilities for Nybbleist."""

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
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend, Shape, SourceLayout
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.nybbleist.generator", "nybbleist_request"
        ),
        layout=SourceLayout(
            wrap=wrap_chars,
        ),
        shape=Shape.REDUCING,
    )


LANGUAGE = LanguageDeclaration(
    "Nybbleist",
    RuntimeSpec(
        "nybbleist",
        category="stack_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=MachineCapabilities(
            debug=DebugSpec(ip="ip", ip_shape="opaque", memory="memory", stack="stack"),
        ),
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
        note="Each input digit is one byte, read high nybble first.",
    ),
)
