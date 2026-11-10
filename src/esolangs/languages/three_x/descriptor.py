"""Runtime and compiler capabilities for 3x."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import _bracket_literal
from esolangs.languages.three_x.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "3x",
    RuntimeSpec(
        "three_x",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.three_x.generator", "three_x_request"
        ),
        layout_width=False,
        wrap=_bracket_literal,
    ),
)
