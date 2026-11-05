"""Runtime and compiler capabilities for Unlambda."""

from esolangs.generation.wrap import _unlambda
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Unlambda",
    RuntimeSpec(
        "unlambda",
        category="other",
        eof="an exhausted '@' hands its argument v, the spec's branch",
        empty_program="an Unlambda program cannot be empty",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.unlambda.generator", "unlambda", ("truth_table",)
        ),
        wrap=_unlambda,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
