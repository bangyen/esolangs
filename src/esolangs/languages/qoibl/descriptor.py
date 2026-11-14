"""Runtime and compiler capabilities for Qoibl."""

from esolangs.languages.qoibl.lifecycle import CAPABILITIES
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
            "esolangs.languages.qoibl.generator", "qoibl_request"
        ),
        layout_width=True,
        # Not a tree: the table is one binary literal the reads divide down.
        shape=Shape.LOOKUP,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.qoibl.generator", "qoibl_balance_request"
        ),
    )


LANGUAGE = LanguageDeclaration(
    "Qoibl",
    RuntimeSpec(
        "qoibl",
        category="register_based",
        source_policy=LineSourcePolicy(),
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
