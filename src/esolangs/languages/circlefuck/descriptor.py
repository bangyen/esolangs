"""Runtime and compiler capabilities for Circlefuck."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend, Shape
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Circlefuck",
    RuntimeSpec(
        "circlefuck",
        category="tape_based",
        eof="its input command is a no-op at EOF, as the spec says",
        empty_program="Circlefuck program cannot be empty",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.circlefuck.generator", "circlefuck", ("truth_table",)
        ),
        # A sum, not a tree: a lookup over the essential inputs only.
        shape=Shape.REDUCING,
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
