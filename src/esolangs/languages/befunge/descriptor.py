"""Runtime and compiler capabilities for Befunge."""

from esolangs.exceptions import GeneratorCapError
from esolangs.languages.befunge.lifecycle import CAPABILITIES
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import LineSourcePolicy, RuntimeSpec
from esolangs.runtime.source_hints import with_hint

MAX_INPUTS = 13


def check_arity(inputs: int) -> None:
    """Refuse a table that cannot fit the fixed grid."""
    if inputs > MAX_INPUTS:
        raise with_hint(
            GeneratorCapError(
                "Befunge supports at most thirteen inputs on its 80x25 grid"
            ),
            (
                "check another generator's limits; width "
                "cannot enlarge Befunge's fixed 80x25 grid"
            ),
        )


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.registry._backend import BooleanBackend, ConstructedLayout, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        max_inputs=MAX_INPUTS,
        arity_guard=check_arity,
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.befunge.generator", "befunge_request"
        ),
        layout=ConstructedLayout(
            layout_balance=True,
            no_wrap="a row is a grid row and the lookup table is indexed by column",
            grid=True,
        ),
        # Not a tree: reads a packed grid cell with ``g``.
        shape=Shape.LOOKUP,
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
    ).with_native_plan(),
    backend=DeferredBackend(_backend),
    # ``.`` writes the digit and a trailing space, so the committed
    # answer carries it and the sweep strips it.
    example=Example(expected="0 "),
)
