"""Runtime and compiler capabilities for Packlang."""

from esolangs.languages.packlang.dialect import (
    LITERAL_POLICIES,
    PacklangLiterals,
)
from esolangs.languages.packlang.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec


def _dialect(literal_policy: str = "decimal") -> None:
    """Validate how Packlang reads a literal of only 0s and 1s."""
    PacklangLiterals(policy=literal_policy)


LANGUAGE = Language(
    "Packlang",
    RuntimeSpec(
        "packlang",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="variable_based",
        dialect=_dialect,
        dialect_values={"literal_policy": LITERAL_POLICIES},
        dialect_defaults={"literal_policy": "decimal"},
        eof="an exhausted charGet is newline byte 10",
        empty_program="empty program",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.packlang.generator",
            "packlang",
            ("truth_table", "width", "literal_policy"),
        ),
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
        balance=FunctionRef(
            "esolangs.languages.packlang.generator",
            "balance_packlang",
            ("_table", "default"),
        ),
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
