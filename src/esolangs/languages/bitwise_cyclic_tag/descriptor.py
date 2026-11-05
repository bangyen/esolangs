"""Runtime and compiler capabilities for Bitwise Cyclic Tag."""

from esolangs.generation.wrap import wrap_chars
from esolangs.languages.bitwise_cyclic_tag.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

PAIR = ("0", "1")


LANGUAGE = Language(
    "Bitwise Cyclic Tag",
    RuntimeSpec(
        "bitwise_cyclic_tag",
        category="queue_based",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.bitwise_cyclic_tag.generator",
            "bitwise_cyclic_tag",
            ("truth_table",),
        ),
        # A positional walk, not a tree of callable residuals.
        shape=Shape.LOOKUP,
        # Safe anywhere: every space and newline is stripped before parsing.
        wrap=wrap_chars,
        template=TemplateSpec(pair=PAIR),
    ),
    contract=BooleanContract(
        note="Bitwise Cyclic Tag has no I/O vocabulary at all: the inputs "
        "are bits of the initial data-string, and the answer is the "
        "bit the last 0 deletes, which the interpreter prints alone -- "
        "so the output is the answer and there is no position to name",
    ),
)
