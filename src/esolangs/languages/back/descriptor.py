"""Runtime and compiler capabilities for Back."""

from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

PAIR = ("-", "+")


LANGUAGE = Language(
    "Back",
    RuntimeSpec(
        "back",
        category="tape_based",
        split=True,
        empty_program="Back program cannot be empty",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.back.generator", "back", ("truth_table", "width")
        ),
        balance=FunctionRef(
            "esolangs.languages.back.generator", "_balance", ("table", "default")
        ),
        no_wrap="the beam path and embedded input occupy fixed grid coordinates",
        template=TemplateSpec(pair=PAIR),
        grid=True,
    ),
    contract=BooleanContract(
        answer_mode="dump",
        note="Back has no output instruction and dumps its tape at halt; "
        "the answer is cell n; earlier cells are input storage or scratch",
    ),
    example=Example(expected="1 0 0"),
)
