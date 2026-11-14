"""Runtime and compiler capabilities for Befunge."""

from esolangs.languages.befunge.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import LineSourcePolicy, RuntimeSpec

MAX_INPUTS = 13


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        max_inputs=MAX_INPUTS,
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.befunge.generator", "befunge_request"
        ),
        layout_width=True,
        # Not a tree: reads a packed grid cell with ``g``.
        shape=Shape.LOOKUP,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.befunge.generator", "befunge_balance_request"
        ),
        no_wrap="a row is a grid row and the lookup table is indexed by column",
        grid=True,
    )


LANGUAGE = LanguageDeclaration(
    "Befunge",
    RuntimeSpec(
        "befunge",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
        source_policy=LineSourcePolicy(),
        empty_program="Befunge program cannot be empty",
    ),
    backend=DeferredBackend(_backend),
    # ``.`` writes the digit and a trailing space, so the committed
    # answer carries it and the sweep strips it.
    example=Example(expected="0 "),
)
