"""Runtime and compiler capabilities for Cyclic tag."""

from esolangs.languages.cyclic_tag.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import BackendDefinition, DeferredBackend, Language
from esolangs.runtime._definition import RuntimeSpec

PAIR = ("0", "1")


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.generation.wrap import wrap_chars
    from esolangs.registry._backend import BooleanBackend, Shape, TemplateSpec
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.cyclic_tag.generator", "cyclic_tag_request"
        ),
        layout_width=False,
        # A positional production walk, not a tree of callable residuals.
        shape=Shape.LOOKUP,
        wrap=wrap_chars,
        template=TemplateSpec(pair=PAIR),
    )


LANGUAGE = Language(
    "Cyclic tag",
    RuntimeSpec(
        "cyclic_tag",
        completion_entrypoint="_execute",
        machine_preparation="prepare_machine",
        capabilities=CAPABILITIES,
        category="queue_based",
        empty_program="Cyclic tag requires productions,queue using bits and semicolons",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        note="Inputs fill the initial queue; the final deleted bit is the answer.",
    ),
)
