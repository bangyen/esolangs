"""Runtime and compiler capabilities for INTERCAL."""

from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

PAIR = ("#0", "#1")


TEMPLATE_CHAR = "@"


LANGUAGE = Language(
    "INTERCAL",
    RuntimeSpec(
        "intercal",
        category="variable_based",
        random=True,
        empty_program="INTERCAL program is insufficiently or excessively polite (E099)",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.intercal.generator",
            "intercal",
            ("truth_table", "width"),
        ),
        same_layout=FunctionRef(
            "esolangs.languages.intercal.generator",
            "_same_layout",
            ("template", "_plain", "layout"),
        ),
        balance=FunctionRef(
            "esolangs.languages.intercal.generator",
            "balance_intercal",
            ("_table", "default"),
        ),
        template=TemplateSpec(pair=PAIR, char=TEMPLATE_CHAR),
    ),
    contract=BooleanContract(
        answer_pattern=r"(?s)^(_\n|I)\n$",
        answer_values=("_\n", "I"),
        note="INTERCAL READ OUT prints a lone overbar for zero and I for one",
    ),
    example=Example(expected="_\n\n"),
)
