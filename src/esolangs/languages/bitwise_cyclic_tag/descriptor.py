"""Runtime and compiler capabilities for Bitwise Cyclic Tag."""

from esolangs.languages.bitwise_cyclic_tag.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import (
    BackendDefinition,
    DeferredBackend,
    LanguageDeclaration,
)
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
            "esolangs.languages.bitwise_cyclic_tag.generator",
            "bitwise_cyclic_tag_request",
        ),
        layout_width=False,
        # A positional walk, not a tree of callable residuals.
        shape=Shape.LOOKUP,
        # Safe anywhere: every space and newline is stripped before parsing.
        wrap=wrap_chars,
        template=TemplateSpec(pair=PAIR),
    )


LANGUAGE = LanguageDeclaration(
    "Bitwise Cyclic Tag",
    RuntimeSpec(
        "bitwise_cyclic_tag",
        category="queue_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(
        note="Bitwise Cyclic Tag has no I/O vocabulary at all: the inputs "
        "are bits of the initial data-string, and the answer is the "
        "bit the last 0 deletes, which the interpreter prints alone -- "
        "so the output is the answer and there is no position to name",
    ),
)
