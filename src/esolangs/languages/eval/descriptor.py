"""Runtime and compiler capabilities for Eval."""

from esolangs.generation.wrap import _quote_literal
from esolangs.registry._backend import BooleanBackend, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Eval",
    RuntimeSpec("eval", category="stack_based"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.eval.generator", "eval", ("truth_table",)
        ),
        # Print through a literal that must not be broken.
        wrap=_quote_literal,
        template=TemplateSpec(
            setters=FunctionRef(
                "esolangs.languages.eval.generator", "eval_setters", ("template", "n")
            )
        ),
    ),
    contract=BooleanContract(),
)
