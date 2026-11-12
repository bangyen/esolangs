"""Registry of language metadata, used by the API, tools, and tests."""

from __future__ import annotations

import re
from collections.abc import Mapping
from functools import cache
from types import MappingProxyType
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from esolangs._bindings import Setters
from esolangs.exceptions import TemplateError, UnknownLanguageError
from esolangs.registry._catalog import Catalog, get_catalog
from esolangs.registry._language import Language
from esolangs.registry._slug import SUGGESTION_CUTOFF, canonical_id
from esolangs.runtime._definition import SourceKind

__all__ = [
    "BY_BOOLEAN",
    "CATALOG",
    "INTERPRETERS",
    "LANGUAGES",
    "SUGGESTION_CUTOFF",
    "Catalog",
    "Generator",
    "Language",
    "SourceKind",
    "canonical_id",
    "example_stems",
    "get_catalog",
    "parameterized_ids",
    "render_template",
    "resolve",
    "template_char",
    "template_setters",
    "wiki_url",
]


if TYPE_CHECKING:
    from esolangs.registry._backend import Generator as Generator
    from esolangs.registry._backend import TemplateSpec
    from esolangs.registry._table import CATALOG as CATALOG
    from esolangs.registry._table import LANGUAGES as LANGUAGES

    BY_BOOLEAN: Mapping[str, Language]
    INTERPRETERS: Mapping[str, str]


def __getattr__(name: str) -> Any:
    """Load installed declarations and compiler types only when requested."""
    value: Any
    if name == "Generator":
        from esolangs.registry._backend import Generator

        value = Generator
    elif name in {"CATALOG", "LANGUAGES", "BY_BOOLEAN", "INTERPRETERS"}:
        catalog = get_catalog()
        value = {
            "CATALOG": catalog,
            "LANGUAGES": catalog.languages,
            "BY_BOOLEAN": catalog.by_boolean,
            "INTERPRETERS": catalog.interpreters,
        }[name]
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)


@cache
def example_stems(*, catalog: Catalog | None = None) -> Mapping[str, str]:
    """Return example stems from declarations without importing example builders."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    stems = {}
    for lang in catalog.languages.values():
        if lang.backend is None or lang.runtime.interpreter is None:
            continue
        # Windows rejects punctuation such as `?`; slash names also need ids.
        stem = lang.name.lower().replace(" ", "-")
        stems[lang.id] = (
            lang.id.replace("_", "-") if re.search(r'[/*()+<>:"\\|?]', stem) else stem
        )
    return MappingProxyType(stems)


def _reads_inputs(language_id: str) -> TemplateError:
    """Refuse a template operation on a language that reads its inputs."""
    return TemplateError(f"{language_id} reads its inputs rather than embedding them")


def template_char(language_id: str, *, catalog: Catalog | None = None) -> str | None:
    """Return the character ``language_id``'s templates spell inputs with."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    template = _template(language_id, catalog=catalog)
    return None if template is None else template.char


def _template(
    language_id: str, *, catalog: Catalog | None = None
) -> TemplateSpec | None:
    """Return a backend's input binding declaration using the existing id index."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    name = catalog.by_id.get(language_id)
    if name is None:
        return None
    backend = catalog.languages[name].backend
    return None if backend is None else backend.template


def template_setters(
    language_id: str, template: str, n: int, *, catalog: Catalog | None = None
) -> Setters:
    """Return the ``(zero, one)`` pairs ``template`` fills its ``n`` inputs with.

    ``template`` is the generator's own output (slots, before rendering)
    or the rendered run form -- the setters read what they need from it,
    which for the two-route generators is the route's prefix.
    """
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    spec = _template(language_id, catalog=catalog)
    if spec is None:
        raise TemplateError(f"unknown language: {language_id}")
    return spec.bindings(template, n)


def render_template(
    language_id: str,
    slots: str,
    n: int,
    *,
    catalog: Catalog | None = None,
) -> tuple[str, str, Setters]:
    """Return ``(text, char, setters)`` for a generator's laid-out slots."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    char = template_char(language_id, catalog=catalog)
    if char is None:
        raise _reads_inputs(language_id)
    return slots, char, template_setters(language_id, slots, n, catalog=catalog)


def parameterized_ids(*, catalog: Catalog | None = None) -> frozenset[str]:
    """Return the canonical ids whose boolean generator emits a template."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    return frozenset(
        lang.id for lang in catalog.languages.values() if lang.parameterized
    )


# Canonical id -> display name, the index :func:`resolve` matches against.
#: Characters a wiki slug may keep: RFC 3986's unreserved set and sub-delims,
#: so parentheses, ``*``, ``~`` and ``-`` stay readable.  ``%`` is the escape
#: character itself and ``^`` is in neither set, so a name carrying either
#: went out escaped and the wiki answered 400.  Non-ASCII is escaped too:
#: a non-ASCII name as raw bytes is served by a browser and refused by a strict one.
_WIKI_SAFE = "_-.~()*!'+,;=:@&$"


def wiki_url(name: str) -> str:
    """Return the esolangs.org page for a language's display name.

    One function because there were two constructions -- :func:`describe`
    built the URL inline and ``scripts/docs/generate.py docs`` built it
    again for the README -- so the same broken link shipped in both, and a
    fix to either would have left the other wrong.
    """
    slug = quote(name.replace(" ", "_"), safe=_WIKI_SAFE)
    return f"https://esolangs.org/wiki/{slug}"


def resolve(name: str, *, catalog: Catalog | None = None) -> str:
    """Resolve a language name within the selected immutable catalog."""
    return get_catalog(catalog).resolve(name)
