"""Runtime and compiler capabilities for Home Row."""

from esolangs.generation.wrap import wrap_chars
from esolangs.registry._backend import BooleanBackend, Shape, TemplateSpec
from esolangs.registry._contracts import BooleanContract
from esolangs.registry._functions import FunctionRef
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec

HOME_ROW_PAIR = ("s", "j")


LANGUAGE = Language(
    "Home Row",
    RuntimeSpec("home_row", category="tape_based"),
    backend=BooleanBackend(
        entrypoint=FunctionRef(
            "esolangs.languages.home_row.generator", "home_row", ("truth_table",)
        ),
        # A sum, not a tree: a lookup over the essential inputs only.
        shape=Shape.REDUCING,
        wrap=wrap_chars,
        template=TemplateSpec(pair=HOME_ROW_PAIR),
    ),
    contract=BooleanContract(),
)
