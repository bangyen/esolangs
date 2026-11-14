"""Runtime and compiler capabilities for CARP."""

from esolangs.exceptions import GeneratorCapError
from esolangs.languages.carp.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime.source_hints import with_hint

MAX_INPUTS = 14


def check_arity(inputs: int) -> None:
    """Refuse more inputs than the register-based construction supports."""
    if inputs > MAX_INPUTS:
        raise with_hint(
            GeneratorCapError("CARP has 15 registers: at most fourteen inputs"),
            "r15 holds the jump constant; inputs take r1..r14",
        )


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.carp.generator", "carp_request"
        ),
        layout_width=False,
        max_inputs=MAX_INPUTS,
        arity_guard=check_arity,
        no_wrap="a line break ends an instruction",
    )


LANGUAGE = LanguageDeclaration(
    "CARP",
    RuntimeSpec(
        "carp",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
        empty_program="a program needs at least one instruction",
    ),
    backend=DeferredBackend(_backend),
)
