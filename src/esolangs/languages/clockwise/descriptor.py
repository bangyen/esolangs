"""Runtime and compiler capabilities for Clockwise."""

from esolangs.languages.clockwise.lifecycle import CAPABILITIES
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
            "esolangs.languages.clockwise.generator", "clockwise_request"
        ),
        layout_width=True,
        # Not a tree: a countdown stops on the entry's own column.
        shape=Shape.LOOKUP,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.clockwise.generator", "clockwise_balance_request"
        ),
        no_wrap="a row is a ring row; the walk's turns sit at fixed cells",
        grid=True,
    )


LANGUAGE = LanguageDeclaration(
    "Clockwise",
    RuntimeSpec(
        "clockwise",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        source_policy=LineSourcePolicy(),
        empty_program="Clockwise program cannot be empty",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream_cyclic",
        note="Clockwise reads all its input bits in one go, so they go "
        "on one line -- one character per bit, not a line per bit, and "
        "not seven bits packed into a character: that packing is real "
        "but is on the output side. A line per bit, or a packed one, "
        "is read as a different row and answered wrongly",
    ),
)
