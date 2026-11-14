"""Runtime and compiler capabilities for Packlang."""

from esolangs._dialect import DialectSchema
from esolangs.languages.packlang.dialect import (
    LITERAL_POLICIES,
    PacklangLiterals,
)
from esolangs.languages.packlang.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
from esolangs.runtime._definition import RuntimeSpec


def _dialect(literal_policy: str = "decimal") -> None:
    """Validate how Packlang reads a literal of only 0s and 1s."""
    PacklangLiterals(policy=literal_policy)


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import BalanceRequest, GenerationRequest
    from esolangs.registry._backend import BooleanBackend, Shape
    from esolangs.registry._functions import FunctionRef
    from esolangs.registry._operations import OperationRef
    from esolangs.runtime._program import Program

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.packlang.generator", "packlang_request"
        ),
        layout_width=True,
        # Not a tree: one painted array cell per differing row, read by index.
        shape=Shape.LOOKUP,
        # One statement a line; each folds on its own.
        # Generators emit indented blocks; fold only an over-wide line.
        # Packlang punctuation separates tokens even without a space.
        wrap=FunctionRef(
            "esolangs.languages.packlang.wrapping", "_packlang", ("program", "width")
        ),
        wrap_multiline=True,
        same_layout=FunctionRef(
            "esolangs.generation.helpers",
            "same_ignoring_whitespace",
            ("template", "plain", "_layout"),
        ),
        balance=OperationRef[BalanceRequest, Program](
            "esolangs.languages.packlang.generator", "packlang_balance_request"
        ),
    )


LANGUAGE = LanguageDeclaration(
    "Packlang",
    RuntimeSpec(
        "packlang",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="variable_based",
        dialect=_dialect,
        dialect_schema=DialectSchema(
            "Packlang",
            {"literal_policy": LITERAL_POLICIES},
            {"literal_policy": "decimal"},
        ),
        eof="an exhausted charGet is newline byte 10",
        empty_program="empty program",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
