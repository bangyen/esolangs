"""Runtime and compiler capabilities for Cyclic tag."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend, Shape, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

PAIR = ("0", "1")


LANGUAGE = Language(
    "Cyclic tag",
    RuntimeSpec(
        "cyclic_tag",
        completion_entrypoint="_execute",
        category="queue_based",
        empty_program="Cyclic tag requires productions,queue using bits and semicolons",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.cyclic_tag.generator", "cyclic_tag", ("truth_table",)
        ),
        # A positional production walk, not a tree of callable residuals.
        shape=Shape.LOOKUP,
        wrap=wrap_chars,
        template=TemplateSpec(pair=PAIR),
    ),
    contract=BooleanContract(
        note="Inputs fill the initial queue; the final deleted bit is the answer.",
    ),
)
