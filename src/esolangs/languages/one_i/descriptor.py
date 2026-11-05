"""Runtime and compiler capabilities for 1 + i."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "1 + i",
    RuntimeSpec("one_i", category="stack_based"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.one_i.generator", "one_i", ("truth_table",)
        ),
        wrap=wrap_chars,
    ),
)
