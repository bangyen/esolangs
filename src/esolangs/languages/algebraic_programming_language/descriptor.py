"""Runtime and compiler capabilities for Algebraic Programming Language."""

from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "Algebraic Programming Language",
    RuntimeSpec("algebraic_programming_language", category="variable_based"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.algebraic_programming_language.generator",
            "algebraic_programming_language",
            ("truth_table", "width"),
        ),
        balance=FunctionRef(
            "esolangs.languages.algebraic_programming_language.generator",
            "balance_apl",
            ("table", "default"),
        ),
        no_wrap="a line with '=' defines, one without runs",
    ),
    contract=BooleanContract(
        note="an executed line prints its result, so the answer ends in a newline",
    ),
    # An executed line prints its result and nothing else, so the
    # answer arrives with the newline that ends that line.
    example=Example(expected="0\n"),
)
