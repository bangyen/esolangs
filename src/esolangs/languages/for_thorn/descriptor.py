"""Runtime and compiler capabilities for Forþ."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Forþ",
    RuntimeSpec("for_thorn", category="stack_based"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.for_thorn.generator", "for_thorn", ("truth_table",)
        ),
        wrap=wrap_chars,
    ),
)
