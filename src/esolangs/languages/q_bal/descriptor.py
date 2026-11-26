"""Runtime and compiler capabilities for Q-BAL."""

from esolangs.languages.q_bal.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.q_bal.generator", "q_bal_request"
        ),
        layout_width=False,
        no_wrap="each line is one statement and a break splits it",
        # One attachment: the table is an integer shifted by the row.
        shape=Shape.LOOKUP,
    )


LANGUAGE = LanguageDeclaration(
    "Q-BAL",
    RuntimeSpec(
        "q_bal",
        category="queue_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
    # ``v -> out`` ends the number with a newline.
    example=Example(expected="0\n"),
)
