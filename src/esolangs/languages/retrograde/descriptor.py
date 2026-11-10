"""Runtime and compiler capabilities for Retrograde."""

from esolangs.generation.requests import GenerationRequest
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.retrograde.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import Language
from esolangs.registry._operations import OperationRef
from esolangs.runtime._definition import RuntimeSpec
from esolangs.runtime._program import Program

PAIR = ("\\", "*")


LANGUAGE = Language(
    "Retrograde",
    RuntimeSpec(
        "retrograde",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="tape_based",
    ),
    backend=BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, Program](
            "esolangs.languages.retrograde.generator", "retrograde_request"
        ),
        layout_width=False,
        wrap=wrap_chars,
        template=TemplateSpec(pair=PAIR),
    ),
    contract=BooleanContract(
        answer_mode="dump",
        note="Inputs are ordered one-instruction setters; the final current "
        "tape bit is the whole answer dump.",
    ),
)
