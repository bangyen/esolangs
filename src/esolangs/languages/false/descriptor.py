"""Runtime and compiler capabilities for FALSE."""

from esolangs.generation.wrap import _false
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._certification import CertificationSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "FALSE",
    RuntimeSpec(
        "false", category="stack_based", eof="an exhausted '^' is the spec's -1"
    ),
    certification=CertificationSpec(reader_checked=True),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.false.generator", "false", ("truth_table", "width")
        ),
        # ``'x`` and ``.x``/``?x`` take the character after them.
        wrap=_false,
        balance=FunctionRef(
            "esolangs.languages.false.generator", "_balance", ("_table", "default")
        ),
    ),
    contract=BooleanContract(
        input_shape="char_stream",
    ),
)
