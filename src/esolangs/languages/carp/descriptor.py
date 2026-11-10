"""Runtime and compiler capabilities for CARP."""

from esolangs.generation.requests import GenerationRequest
from esolangs.languages.carp.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

MAX_INPUTS = 14


LANGUAGE = Language(
    "CARP",
    RuntimeSpec(
        "carp",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
        empty_program="a program needs at least one instruction",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.carp.generator", "carp_request"
        ),
        layout_width=False,
        max_inputs=MAX_INPUTS,
        no_wrap="a line break ends an instruction",
    ),
)
