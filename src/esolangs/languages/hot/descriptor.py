"""Runtime and compiler capabilities for Hot."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.hot.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Hot",
    RuntimeSpec(
        "hot",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        eof="the stream past the input string is 0 bits",
        empty_program="a Hot program needs at least one combinator",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.hot.generator", "hot_request"
        ),
        layout_width=False,
        wrap=wrap_chars,
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
