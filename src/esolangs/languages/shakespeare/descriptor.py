"""Runtime and compiler capabilities for Shakespeare."""

from esolangs.generation.wrap import wrap_space_delimited
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Shakespeare",
    RuntimeSpec(
        "shakespeare",
        category="stack_based",
        empty_program="Shakespeare line 1: empty play",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.shakespeare.generator", "shakespeare", ("truth_table",)
        ),
        shape=Shape.LOOKUP,
        wrap=wrap_space_delimited,
    ),
)
