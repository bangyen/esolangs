"""Runtime and compiler capabilities for Basicfuck."""

from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Basicfuck",
    RuntimeSpec(
        "basicfuck",
        category="tape_based",
        empty_program="missing directive or #allocate",
        eof="`read` at EOF raises: the page's cat covers three EOF conventions",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.basicfuck.generator", "basicfuck", ("truth_table",)
        ),
        no_wrap="the directive and #allocate are lines one and two",
    ),
    contract=BooleanContract(input_shape="char_stream"),
    example=Example(expected="0"),
)
