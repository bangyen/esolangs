"""Runtime and compiler capabilities for Kiss."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.kiss.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Kiss",
    RuntimeSpec(
        "kiss",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        empty_program="a Kiss program needs at least one combinator",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.kiss.generator", "kiss_request"
        ),
        layout_width=False,
        wrap=wrap_chars,
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
