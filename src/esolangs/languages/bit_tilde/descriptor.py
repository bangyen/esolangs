"""Runtime and compiler capabilities for bit~."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "bit~",
    RuntimeSpec("bit_tilde", category="tape_based"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.bit_tilde.generator", "bit_tilde", ("truth_table",)
        ),
        # Not a tree: planted entries a Horner jump addresses.
        shape=Shape.LOOKUP,
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
