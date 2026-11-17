"""Runtime and compiler capabilities for Help."""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._lifecycle import Completion


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.help.generator", "help_request"
        ),
        shape=Shape.REDUCING,
        no_wrap="line breaks end instructions and change jump addresses",
    )


LANGUAGE = LanguageDeclaration(
    "Help.",
    RuntimeSpec(
        "help",
        category="register_based",
        random=True,
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=MachineCapabilities(
            completion=Completion.HALTED,
            eof_is_a_value=False,
            debug=DebugSpec(ip="ip", memory="_debug_memory", memory_at="memory_at"),
        ),
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(input_shape="char_stream"),
)
