"""Runtime and compiler capabilities for Thue."""

from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._certification import CertificationSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Thue",
    RuntimeSpec(
        "thue",
        category="program_based",
        random=True,
        empty_program=(
            "a Thue program needs a '::=' line with nothing but whitespace on "
            "either side, to separate its rules from its starting state"
        ),
    ),
    certification=CertificationSpec(reader_checked=True),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.thue.generator", "thue", ("truth_table", "width")
        ),
        # Not a tree: the table is the state, and each read halves it.
        shape=Shape.LOOKUP,
        balance=FunctionRef(
            "esolangs.languages.thue.generator",
            "balance_thue",
            ("truth_table", "default"),
        ),
        no_wrap="a newline ends a rule, and the state's own newlines are part of it",
    ),
    contract=BooleanContract(
        note="Thue draws which rewrite to make, by spec, and the "
        "interpreter draws too; this program's rules are written so that "
        "every state it reaches has exactly one, leaving the draw nothing "
        "to change",
    ),
)
