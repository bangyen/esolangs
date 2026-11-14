"""Runtime and compiler capabilities for Fish."""

from esolangs.languages.fish.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import LineSourcePolicy, RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.fish.generator", "fish_request"
        ),
        layout_width=True,
        # Not a tree: an indexed table read.
        shape=Shape.LOOKUP,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.fish.generator", "fish_balance_request"
        ),
        no_wrap="a row is a codebox row and the lookup table is indexed by column",
        grid=True,
    )


LANGUAGE = LanguageDeclaration(
    "Fish",
    RuntimeSpec(
        "fish",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
        source_policy=LineSourcePolicy(),
        eof="an exhausted 'i' is the spec's -1",
        empty_program="Fish program cannot be empty",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
