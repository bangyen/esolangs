"""Runtime and compiler capabilities for Subleq."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import wrap_grid
from esolangs.languages.subleq.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Subleq",
    RuntimeSpec(
        "subleq",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="tape_based",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.subleq.generator", "subleq_request"
        ),
        layout_width=False,
        # Shared tree or packed lookup.
        shape=Shape.LOOKUP,
        wrap=wrap_grid,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
