"""Runtime and compiler capabilities for NQ."""

from esolangs._dialect import DialectSchema
from esolangs.generation.wrap import wrap_chars
from esolangs.languages.nq.dialect import DEFAULT_GUARD_BINDING, GUARD_BINDINGS
from esolangs.languages.nq.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Example, Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "NQ",
    RuntimeSpec(
        "nq",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="queue_based",
        dialect=FunctionRef(
            "esolangs.languages.nq.interpreter", "guard_dialect", ("guard_binding",)
        ),
        dialect_schema=DialectSchema(
            "NQ",
            {"guard_binding": GUARD_BINDINGS},
            {"guard_binding": DEFAULT_GUARD_BINDING},
        ),
        machine_preparation="prepare_machine",
    ),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.nq.generator", "nq", ("truth_table", "guard_binding")
        ),
        wrap=wrap_chars,
    ),
    contract=BooleanContract(
        input_shape="char_stream",
        answer_pattern="([ #])",
        answer_values=(" ", "#"),
        note="The whole output is a space for false or # for true.",
        ignores_whitespace=True,
    ),
    example=Example(expected=" "),
)
