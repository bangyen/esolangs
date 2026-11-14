"""Runtime and compiler capabilities for Basicfuck."""

from esolangs.languages.basicfuck.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.basicfuck.generator", "basicfuck_request"
        ),
        layout_width=False,
        no_wrap="the directive and #allocate are lines one and two",
    )


LANGUAGE = LanguageDeclaration(
    "Basicfuck",
    RuntimeSpec(
        "basicfuck",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="tape_based",
        empty_program="missing directive or #allocate",
        eof="`read` at EOF raises: the page's cat covers three EOF conventions",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(input_shape="char_stream"),
    example=Example(expected="0"),
)
