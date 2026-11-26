"""Runtime and compiler capabilities for Bifunge."""

from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._capabilities import DebugSpec, MachineCapabilities
from esolangs.runtime._definition import LineSourcePolicy, RuntimeSpec
from esolangs.runtime._lifecycle import Completion


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.bifunge.generator", "bifunge_request"
        ),
        shape=Shape.TREE,
        grid=True,
        no_wrap="a line break moves the 2x2 commands",
    )


LANGUAGE = LanguageDeclaration(
    "Bifunge",
    RuntimeSpec(
        "bifunge",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=MachineCapabilities(
            completion=Completion.HALTED,
            eof_is_a_value=False,
            debug=DebugSpec(ip="ip", ip_shape="grid", stack="stack"),
        ),
        source_policy=LineSourcePolicy(),
        empty_program="Bifunge program cannot be empty",
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(input_shape="char_stream"),
)
