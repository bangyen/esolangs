"""Runtime and compiler capabilities for IEBEL."""

from esolangs.generation.requests import GenerationRequest
from esolangs.languages.iebel.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "IEBEL",
    RuntimeSpec(
        "iebel",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="register_based",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.iebel.generator", "iebel_request"
        ),
        layout_width=False,
        no_wrap="each line is one instruction; a break splits its fields",
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
