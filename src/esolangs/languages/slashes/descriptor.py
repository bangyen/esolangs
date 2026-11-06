"""Runtime and compiler capabilities for ///."""

from esolangs.languages.slashes.lifecycle import CAPABILITIES
from esolangs.registry._backend import BooleanBackend, Shape, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

LANGUAGE = Language(
    "///",
    RuntimeSpec(
        "slashes",
        machine_preparation="prepare_machine",
        completion_entrypoint="_execute",
        capabilities=CAPABILITIES,
        category="program_based",
        path_like_source=True,
    ),
    id="slashes",
    aliases=("Slashalash",),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.slashes.generator", "slashes", ("truth_table",)
        ),
        # Not a tree: an indexed table rewrite.
        shape=Shape.LOOKUP,
        no_wrap="newlines are literal output and substitution data",
        wrap_balance=FunctionRef(
            "esolangs.languages.slashes.generator", "_balance", ("program",)
        ),
        template=TemplateSpec(
            pair=("a", "b"),
            unfilled=FunctionRef(
                "esolangs.languages.slashes.generator",
                "_is_unfilled_template",
                ("code",),
            ),
        ),
    ),
    contract=BooleanContract(
        note="Inputs fill the binary row index before unary selection; "
        "constant tables parse the input letters as a nonmatching rule pattern.",
    ),
)
