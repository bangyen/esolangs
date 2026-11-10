"""Runtime and compiler capabilities for bit~."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.bit_tilde.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "bit~",
    RuntimeSpec(
        "bit_tilde",
        category="tape_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.bit_tilde.generator", "bit_tilde_request"
        ),
        layout_width=False,
        # Not a tree: planted entries a Horner jump addresses.
        shape=Shape.LOOKUP,
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
