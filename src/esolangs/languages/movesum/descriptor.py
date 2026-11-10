"""Runtime and compiler capabilities for Movesum."""

from esolangs.generation.requests import GenerationRequest
from esolangs.languages.movesum.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._language import Example, Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Movesum",
    RuntimeSpec(
        "movesum",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="tape_based",
        eof="a read at EOF is 0",
        empty_program="Movesum program is empty",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.movesum.generator", "movesum_request"
        ),
        layout_width=False,
        # Not a tree: one rung per row, whatever the table says.
        shape=Shape.LOOKUP,
        no_wrap="each line is one instruction and a break splits it",
    ),
    example=Example(expected="0 0"),
)
