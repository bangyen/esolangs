"""Runtime and compiler capabilities for Pilas."""

from esolangs.generation.requests import GenerationRequest
from esolangs.languages.pilas.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Pilas",
    RuntimeSpec(
        "pilas",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.pilas.generator", "pilas_request"
        ),
        layout_width=False,
        no_wrap="a newline starts line two, which runs a different stack",
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
