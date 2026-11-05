"""Runtime and compiler capabilities for Unary."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Unary",
    RuntimeSpec(
        "unary", category="tape_based", compressed_source=True, eof="stores zero"
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.unary.generator", "unary", ("truth_table",)
        ),
        max_inputs=9,
        restrictions=(
            "raw export 32 Mi characters; generation 256 Mi characters; "
            "gzip 256 KiB; table-dependent caps"
        ),
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        alphabet=("\x00", "\xff"),
        input_shape="char_stream",
        answer_mode="termination",
        answer_values=("halts", "diverges"),
        note="Bytes 0/255 encode inputs; halt means 0, a fixed cycle means 1.",
    ),
    example=Example(expected="", expected_compared=False, slow_build=True),
)
