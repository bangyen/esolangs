"""Runtime and compiler capabilities for BASICER."""

from esolangs.languages.basicer.lifecycle import CAPABILITIES
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
            "esolangs.languages.basicer.generator", "basicer_request"
        ),
        layout_width=False,
        no_wrap="each line is one instruction and a break splits it",
    )


LANGUAGE = LanguageDeclaration(
    "BASICER",
    RuntimeSpec(
        "basicer",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="program_based",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(alphabet=("1", "2")),
    example=Example(expected="0\n"),
)
