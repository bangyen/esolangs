"""Runtime and compiler capabilities for Caballo."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Caballo",
    RuntimeSpec(
        "caballo",
        category="stack_based",
        random=True,
        eof="the whole input is read once as the initial stack; no read meets EOF",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.caballo.generator", "caballo", ("truth_table",)
        ),
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        answer_mode="dump",
        answer_pattern=r"^(\[\]|\[1\])$",
        answer_values=("[]", "[1]"),
        note="Caballo reads its inputs as the initial stack, the first on "
        "top, and prints the surviving stack: [1] for one, [] for zero",
    ),
    example=Example(expected="[]"),
)
