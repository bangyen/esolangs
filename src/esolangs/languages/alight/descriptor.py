"""Runtime and compiler capabilities for Alight."""

from esolangs._dialect import DialectSchema
from esolangs.languages.alight.dialect import (
    EXPRESSION_SYNTAXES,
    LIST_UPDATES,
)
from esolangs.languages.alight.dialect import (
    expression_syntax as validate_expression_syntax,
)
from esolangs.languages.alight.dialect import (
    list_update as validate_list_update,
)
from esolangs.languages.alight.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import LineSourcePolicy, RuntimeSpec


def _dialect(expression_syntax: str = "infix", list_update: str = "in_place") -> None:
    """Validate Alight's dialect settings, one keyword per setting."""
    validate_expression_syntax(expression_syntax)
    validate_list_update(list_update)


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.alight.generator", "alight_request"
        ),
        layout_width=True,
        # Not a tree: a Horner row index into a string literal.
        shape=Shape.LOOKUP,
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.alight.generator", "alight_balance_request"
        ),
        no_wrap="a command is a word walked cell by cell; a row end cuts it",
    )


LANGUAGE = LanguageDeclaration(
    "Alight",
    RuntimeSpec(
        "alight",
        category="grid_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        dialect=_dialect,
        dialect_schema=DialectSchema(
            "Alight",
            {
                "expression_syntax": EXPRESSION_SYNTAXES,
                "list_update": LIST_UPDATES,
            },
            {"expression_syntax": "infix", "list_update": "in_place"},
        ),
        source_policy=LineSourcePolicy(),
        eof="it raises its own error before the read is reached",
        underfed_raises=True,
        empty_program="empty program",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
