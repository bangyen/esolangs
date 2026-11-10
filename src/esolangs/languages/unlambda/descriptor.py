"""Runtime and compiler capabilities for Unlambda."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import _unlambda
from esolangs.languages.unlambda.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Unlambda",
    RuntimeSpec(
        "unlambda",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        eof="an exhausted '@' hands its argument v, the spec's branch",
        empty_program="an Unlambda program cannot be empty",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.unlambda.generator", "unlambda_request"
        ),
        layout_width=False,
        wrap=_unlambda,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
