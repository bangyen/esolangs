"""Runtime and compiler capabilities for Parenthesys."""

from esolangs.generation.requests import GenerationRequest
from esolangs.languages.parenthesys.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

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
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.parenthesys.generator", "parenthesys_request"
        ),
        layout_width=False,
        # Not a tree: one string literal the row indexes.
        shape=Shape.LOOKUP,
        no_wrap="a line break is a literal: inside the table it shifts every row",
    ),
)
