"""Runtime and compiler capabilities for Object disoriented."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.object_disoriented.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Object disoriented",
    RuntimeSpec(
        "object_disoriented",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="other",
        empty_program="Object disoriented program defines no 'main' class",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.object_disoriented.generator",
            "object_disoriented_request",
        ),
        layout_width=False,
        # Whitespace is ignored everywhere, class names included.
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
        note="Object disoriented reads input bits most significant first, so "
        "a program keeps each input byte's eighth bit and drops the seven before it",
    ),
)
