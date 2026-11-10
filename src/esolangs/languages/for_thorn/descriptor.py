"""Runtime and compiler capabilities for Forþ."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.for_thorn.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

LANGUAGE = Language(
    "Forþ",
    RuntimeSpec(
        "for_thorn",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.for_thorn.generator", "for_thorn_request"
        ),
        layout_width=False,
        wrap=wrap_chars,
    ),
)
