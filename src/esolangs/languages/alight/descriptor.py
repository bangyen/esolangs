"""Runtime and compiler capabilities for Alight."""

from esolangs.languages.alight.interpreter._dialect import (
    EXPRESSION_SYNTAXES,
    LIST_UPDATES,
)
from esolangs.languages.alight.interpreter._dialect import (
    expression_syntax as validate_expression_syntax,
)
from esolangs.languages.alight.interpreter._dialect import (
    list_update as validate_list_update,
)
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec


def _dialect(expression_syntax: str = "infix", list_update: str = "in_place") -> None:
    """Validate Alight's dialect settings, one keyword per setting."""
    validate_expression_syntax(expression_syntax)
    validate_list_update(list_update)


LANGUAGE = Language(
    "Alight",
    RuntimeSpec(
        "alight",
        category="grid_based",
        dialect=_dialect,
        dialect_values={
            "expression_syntax": EXPRESSION_SYNTAXES,
            "list_update": LIST_UPDATES,
        },
        dialect_defaults={"expression_syntax": "infix", "list_update": "in_place"},
        split=True,
        eof="it raises its own error before the read is reached",
        underfed_raises=True,
        empty_program="empty program",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.alight.generator",
            "alight",
            ("truth_table", "width", "expression_syntax", "list_update"),
        ),
        # Not a tree: a Horner row index into a string literal.
        shape=Shape.LOOKUP,
        balance=FunctionRef(
            "esolangs.languages.alight.generator",
            "balance_alight",
            ("table", "default", "expression_syntax"),
        ),
        no_wrap="a command is a word walked cell by cell; a row end cuts it",
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
