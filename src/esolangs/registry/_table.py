"""Every registered language: its interpreter, source shape, and generator.

A language with a generator declares ``LANGUAGE = Language(...)`` at the end
of its generator module (``esolangs.languages.<id>.generator``); this table collects
those.  Only the interpreter-only languages, which have no such module, are
listed here.
"""

from __future__ import annotations

from esolangs.languages.generators import _LANGUAGES
from esolangs.registry._language import Generator, Language, SourceKind

__all__ = ["LANGUAGES", "Generator", "Language", "SourceKind"]

# Interpreter-only entries qualify through the fame route.
_INTERPRETER_ONLY = (
    Language("HQ9+", "hq9", category="register_based", id="hq9"),
    Language("Nope.", "nope", category="other"),
    Language("Deadfish", "deadfish", category="register_based"),
)


LANGUAGES: dict[str, Language] = {
    lang.name: lang
    for lang in sorted(
        (*_LANGUAGES, *_INTERPRETER_ONLY), key=lambda lang: lang.name.casefold()
    )
}
