"""Runtime and compiler capabilities for Fackward."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import TokenWrapper
from esolangs.languages.fackward.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

_wrap = TokenWrapper(r"\d+|[\s\S]")


LANGUAGE = Language(
    "Fackward",
    RuntimeSpec(
        "fackward",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
        eof="a read at EOF halts the run",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.fackward.generator", "fackward_request"
        ),
        layout_width=False,
        # Whitespace only separates tokens, so a newline between two is harmless.
        wrap=_wrap,
    ),
    contract=BooleanContract(input_shape="char_stream"),
)
