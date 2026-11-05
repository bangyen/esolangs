"""Runtime and compiler capabilities for Suffolk."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Suffolk",
    RuntimeSpec(
        "suffolk",
        category="tape_based",
        # Reads until the input runs out and treats that as its stop, which is
        # how its generated programs terminate at all.
        eof="reads to exhaustion, so EOF is the halt",
        empty_program="Suffolk program cannot be empty",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.suffolk.generator", "suffolk", ("truth_table",)
        ),
        # Both routes project to the essential inputs.
        shape=Shape.REDUCING,
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
