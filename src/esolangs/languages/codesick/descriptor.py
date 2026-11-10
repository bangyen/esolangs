"""Runtime and compiler capabilities for Codesick."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import wrap_space_delimited
from esolangs.languages.codesick.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Codesick",
    RuntimeSpec(
        "codesick",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        eof="the whole input is read once to replace every `in`; no read meets EOF",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.codesick.generator", "codesick_request"
        ),
        layout_width=False,
        # An argument holds no whitespace, so break only between arguments.
        wrap=wrap_space_delimited,
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
