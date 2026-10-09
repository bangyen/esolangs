"""Every registered language: its interpreter, source shape, and generator.

A language with a generator declares ``LANGUAGE = Language(...)`` at the end
of its generator module (``esolangs.tools.<module>``); this table collects
those.  Only the interpreter-only languages, which have no such module, are
listed here.
"""

from __future__ import annotations

import sys

# Importing the package imports every generator module, so each ``LANGUAGE``
# is in ``sys.modules`` by the time the table below is built.
from esolangs import tools  # noqa: F401
from esolangs.registry._language import Generator, Language, SourceKind

__all__ = ["LANGUAGES", "Generator", "Language", "SourceKind"]

# Interpreter-only entries qualify through the fame route.
_INTERPRETER_ONLY = (
    Language("HQ9+", "register_based.hq9", id="hq9"),
    Language("Nope.", "other.nope"),
    Language("Unary", "tape_based.unary"),
    Language("Deadfish", "register_based.deadfish"),
)


def _declared() -> list[Language]:
    """Return the ``LANGUAGE`` of every generator module ``tools`` imported."""
    return [
        module.LANGUAGE
        for name, module in sorted(sys.modules.items())
        if name.startswith("esolangs.tools.") and hasattr(module, "LANGUAGE")
    ]


LANGUAGES: dict[str, Language] = {
    lang.name: lang
    for lang in sorted(
        (*_declared(), *_INTERPRETER_ONLY), key=lambda lang: lang.name.casefold()
    )
}
