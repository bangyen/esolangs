"""Every registered language: its interpreter, source shape, and generator.

Generated exports collect generator and independent descriptor declarations.
Only interpreter-only languages remain listed directly here.
"""

from __future__ import annotations

from esolangs.languages.generators import _LANGUAGES
from esolangs.registry._backend import Generator
from esolangs.registry._language import Language
from esolangs.runtime._definition import RuntimeSpec, SourceKind

__all__ = ["LANGUAGES", "Generator", "Language", "SourceKind"]

# Interpreter-only entries qualify through the fame route.
_INTERPRETER_ONLY = (
    Language("HQ9+", RuntimeSpec("hq9", category="register_based"), id="hq9"),
    Language(
        "Nope.",
        RuntimeSpec("nope", category="other"),
    ),
    Language(
        "Deadfish",
        RuntimeSpec("deadfish", category="register_based"),
    ),
)


LANGUAGES: dict[str, Language] = {
    lang.name: lang
    for lang in sorted(
        (*_LANGUAGES, *_INTERPRETER_ONLY), key=lambda lang: lang.name.casefold()
    )
}
