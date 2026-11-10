"""Runtime and compiler capabilities for Between."""

from esolangs.generation.requests import GenerationRequest
from esolangs.languages.between.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Between",
    RuntimeSpec(
        "between",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.between.generator", "between_request"
        ),
        layout_width=False,
        no_wrap="each line is one instruction and a break splits it",
    ),
)
