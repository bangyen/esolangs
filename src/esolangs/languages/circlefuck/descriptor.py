"""Runtime and compiler capabilities for Circlefuck."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.circlefuck.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Circlefuck",
    RuntimeSpec(
        "circlefuck",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="tape_based",
        eof="its input command is a no-op at EOF, as the spec says",
        empty_program="Circlefuck program cannot be empty",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.circlefuck.generator", "circlefuck_request"
        ),
        layout_width=False,
        # A sum, not a tree: a lookup over the essential inputs only.
        shape=Shape.REDUCING,
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
