"""Runtime and compiler capabilities for Parenthesys."""

from esolangs.languages.parenthesys.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Parenthesys",
    RuntimeSpec(
        "parenthesys",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.parenthesys.generator", "parenthesys", ("truth_table",)
        ),
        # Not a tree: one string literal the row indexes.
        shape=Shape.LOOKUP,
        no_wrap="a line break is a literal: inside the table it shifts every row",
    ),
)
