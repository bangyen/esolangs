"""Runtime and compiler capabilities for Object disoriented."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Object disoriented",
    RuntimeSpec(
        "object_disoriented",
        category="other",
        empty_program="Object disoriented program defines no 'main' class",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.object_disoriented.generator",
            "object_disoriented",
            ("truth_table",),
        ),
        # Whitespace is ignored everywhere, class names included.
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
        note="Object disoriented reads input bits most significant first, so "
        "a program keeps each input byte's eighth bit and drops the seven before it",
    ),
)
