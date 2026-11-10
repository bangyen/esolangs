"""Runtime and compiler capabilities for Bleh."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import TokenWrapper
from esolangs.languages.bleh.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

_TOKEN = r'"[^\"]*"|::|\w+|[\s\S]'


LANGUAGE = Language(
    "Bleh",
    RuntimeSpec(
        "bleh",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        eof="an exhausted io::next() is the empty bitstring",
        underfed_raises=True,
        empty_program="a Bleh program needs a main function",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.bleh.generator", "bleh_request"
        ),
        layout_width=False,
        wrap=TokenWrapper(_TOKEN),
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
