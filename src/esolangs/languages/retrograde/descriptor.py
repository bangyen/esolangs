"""Runtime and compiler capabilities for Retrograde."""

from esolangs.languages.retrograde.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import BackendDefinition, DeferredBackend, Language
from esolangs.runtime._definition import RuntimeSpec

PAIR = ("\\", "*")


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend, TemplateSpec
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.retrograde.generator", "retrograde_request"
        ),
        layout_width=False,
        wrap=wrap_chars,
        template=TemplateSpec(pair=PAIR),
    )


LANGUAGE = Language(
    "Retrograde",
    RuntimeSpec(
        "retrograde",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="tape_based",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        answer_mode="dump",
        note="Inputs are ordered one-instruction setters; the final current "
        "tape bit is the whole answer dump.",
    ),
)
