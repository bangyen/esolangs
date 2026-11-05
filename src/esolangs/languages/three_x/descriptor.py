"""Runtime and compiler capabilities for 3x."""

from esolangs.generation.wrap import _bracket_literal
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "3x",
    RuntimeSpec("three_x", category="stack_based"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.three_x.generator", "three_x", ("truth_table",)
        ),
        wrap=_bracket_literal,
    ),
)
