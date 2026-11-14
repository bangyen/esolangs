"""Runtime and compiler capabilities for Interprogck8."""

from esolangs.languages.interprogck8.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import LineSourcePolicy, RuntimeSpec

MAX_INPUTS = 40


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        restrictions=(
            f"at most {MAX_INPUTS} inputs, past any table that fits in memory"
        ),
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.interprogck8.generator", "interprogck8_request"
        ),
        layout_width=False,
        no_wrap="a newline adds a line and moves every DownAccLines landing",
    )


LANGUAGE = LanguageDeclaration(
    "Interprogck8",
    RuntimeSpec(
        "interprogck8",
        completion_entrypoint="_execute_program",
        machine_preparation="prepare_machine",
        capabilities=CAPABILITIES,
        category="register_based",
        source_policy=LineSourcePolicy(),
        random=True,
    ),
    backend=DeferredBackend(_backend),
)
