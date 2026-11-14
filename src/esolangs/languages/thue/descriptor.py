"""Runtime and compiler capabilities for Thue."""

from esolangs.languages.thue.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.thue.generator", "thue_request"
        ),
        layout_width=True,
        # Not a tree: the table is the state, and each read halves it.
        shape=Shape.LOOKUP,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.thue.generator", "thue_balance_request"
        ),
        no_wrap="a newline ends a rule, and the state's own newlines are part of it",
    )


LANGUAGE = LanguageDeclaration(
    "Thue",
    RuntimeSpec(
        "thue",
        category="program_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
        empty_program=(
            "a Thue program needs a '::=' line with nothing but whitespace on "
            "either side, to separate its rules from its starting state"
        ),
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        note="Thue draws which rewrite to make, by spec, and the "
        "interpreter draws too; this program's rules are written so that "
        "every state it reaches has exactly one, leaving the draw nothing "
        "to change",
    ),
)
