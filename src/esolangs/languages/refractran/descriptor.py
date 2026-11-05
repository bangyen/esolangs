"""Runtime and compiler capabilities for REFRACTRAN."""

from esolangs.generation.wrap import wrap_space_delimited
from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

PAIR = ("0", "1")


LANGUAGE = Language(
    "REFRACTRAN",
    RuntimeSpec(
        "refractran",
        category="register_based",
        empty_program="REFRACTRAN needs an initial integer",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.refractran.generator",
            "refractran",
            ("truth_table", "width"),
        ),
        wrap=wrap_space_delimited,
        balance=FunctionRef(
            "esolangs.languages.refractran.generator", "_balance", ("_table", "default")
        ),
        template=TemplateSpec(pair=PAIR),
    ),
    contract=BooleanContract(
        answer_mode="dump",
        answer_pattern=r"([01])$",
        note="Inputs are ordered prime exponents in the initial integer; "
        "the final binary state ends in the answer bit.",
    ),
    example=Example(expected_compared=False),
)
