"""Runtime and compiler capabilities for Eval."""

from esolangs.languages.eval.lifecycle import CAPABILITIES
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._language import BackendDefinition, DeferredBackend, Language
from esolangs.runtime._definition import RuntimeSpec


def _backend() -> BackendDefinition:
    from esolangs.generation.requests import GenerationRequest
    from esolangs.generation.template import TemplateLayout
    from esolangs.generation.wrap import _quote_literal
    from esolangs.registry._backend import BooleanBackend, TemplateSpec
    from esolangs.registry._functions import FunctionRef
    from esolangs.registry._operations import OperationRef

    return BooleanBackend(
        entrypoint=OperationRef[GenerationRequest, TemplateLayout](
            "esolangs.languages.eval.generator", "eval_request"
        ),
        layout_width=False,
        # Print through a literal that must not be broken.
        wrap=_quote_literal,
        template=TemplateSpec(
            setters=FunctionRef(
                "esolangs.languages.eval.generator", "eval_setters", ("template", "n")
            )
        ),
    )


LANGUAGE = Language(
    "Eval",
    RuntimeSpec(
        "eval",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="stack_based",
    ),
    backend=DeferredBackend(_backend),
    contract=BooleanContract(),
)
