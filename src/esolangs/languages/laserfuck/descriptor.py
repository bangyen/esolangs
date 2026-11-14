"""Runtime and compiler capabilities for LaserFuck."""

from esolangs.languages.laserfuck.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import LineSourcePolicy, RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.laserfuck.generator", "laserfuck_request"
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.laserfuck.generator", "laserfuck_balance_request"
        ),
        grid=True,
    )


LANGUAGE = LanguageDeclaration(
    "LaserFuck",
    RuntimeSpec(
        "laserfuck",
        category="grid_based",
        random=True,
        source_policy=LineSourcePolicy(),
        # Seed 2 draws heading 0 (up), matching this language's examples.
        reproducible_seed=2,
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        answer_mode="dump",
        note="the initial heading is random by spec, so the example pins "
        "the source it is drawn from: seed 0 draws heading 3",
        input_shape="char_stream",
    ),
    example=Example(expected="0", kwargs=(("seed", 0),)),
)
