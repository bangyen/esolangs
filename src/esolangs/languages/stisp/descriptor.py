"""Runtime and compiler capabilities for Stisp."""

from esolangs.generation.wrap import TokenWrapper
from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

_TOKEN = r"->|[A-Za-z0-9_]+|[\s\S]"


PAIR = ("0", "1")


LANGUAGE = Language(
    "Stisp",
    RuntimeSpec(
        "stisp",
        category="other",
        empty_program="a Stisp program needs a stack expression",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.stisp.generator", "stisp", ("truth_table",)
        ),
        wrap=TokenWrapper(_TOKEN),
        template=TemplateSpec(pair=PAIR),
    ),
    contract=BooleanContract(
        answer_mode="dump",
        note="Stisp has no input or output: each input is the atom 0 or 1 "
        "in the template, and the result printed at halt is the answer atom",
    ),
)
