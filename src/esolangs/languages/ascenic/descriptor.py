"""Runtime and compiler capabilities for Ascenic."""

from esolangs.generation.requests import GenerationRequest
from esolangs.languages.ascenic.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Ascenic",
    RuntimeSpec(
        "ascenic",
        category="stack_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        random=True,
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.ascenic.generator", "ascenic_request"
        ),
        layout_width=False,
        no_wrap="a line's length is its opcode and argument",
    ),
)
