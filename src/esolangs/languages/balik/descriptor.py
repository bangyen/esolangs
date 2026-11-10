"""Runtime and compiler capabilities for Balik."""

from esolangs.generation.requests import GenerationRequest
from esolangs.languages.balik.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Balik",
    RuntimeSpec(
        "balik",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="grid_based",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.balik.generator", "balik_request"
        ),
        layout_width=False,
        shape=Shape.TREE,
        no_wrap="a newline adds a grid row and moves every vertical path",
    ),
)
