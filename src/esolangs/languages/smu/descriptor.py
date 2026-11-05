"""Runtime and compiler capabilities for Smu."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Smu",
    RuntimeSpec(
        "smu",
        category="stack_based",
        # Every run pushes its input bit, and the spec's EOF bit is ``=``.
        eof="an exhausted read pushes the spec's '=' bit",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.smu.generator", "smu", ("truth_table",)
        ),
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
        note="Smu reads one bit a run, low bit of each byte first, and "
        "packs its output bits into bytes the same way",
    ),
)
