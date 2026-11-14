"""Runtime and compiler capabilities for Algebraic Programming Language."""

from esolangs.languages.algebraic_programming_language.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    Example,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.registry._backend import BooleanBackend
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.algebraic_programming_language.generator",
            "algebraic_programming_language_request",
        ),
        layout_width=True,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.algebraic_programming_language.generator",
            "algebraic_programming_language_balance_request",
        ),
        no_wrap="a line with '=' defines, one without runs",
    )


LANGUAGE = LanguageDeclaration(
    "Algebraic Programming Language",
    RuntimeSpec(
        "algebraic_programming_language",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="variable_based",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        note="an executed line prints its result, so the answer ends in a newline",
    ),
    # An executed line prints its result and nothing else, so the
    # answer arrives with the newline that ends that line.
    example=Example(expected="0\n"),
)
