"""Runtime and compiler capabilities for CARP."""

from esolangs.registry._backend import BooleanBackend
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

MAX_INPUTS = 14


LANGUAGE = Language(
    "CARP",
    RuntimeSpec(
        "carp",
        category="register_based",
        empty_program="a program needs at least one instruction",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.carp.generator", "carp", ("truth_table",)
        ),
        max_inputs=MAX_INPUTS,
        no_wrap="a line break ends an instruction",
    ),
)
