"""Runtime and compiler capabilities for Ascenic."""

from esolangs.registry._backend import BooleanBackend
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Ascenic",
    RuntimeSpec("ascenic", category="stack_based", random=True),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.ascenic.generator", "ascenic", ("truth_table",)
        ),
        no_wrap="a line's length is its opcode and argument",
    ),
)
