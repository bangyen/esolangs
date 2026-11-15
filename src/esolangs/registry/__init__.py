"""Registry of language metadata, used by the API, tools, and tests."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from esolangs._bindings import Setters
from esolangs.exceptions import ArgumentError, TemplateError, UnknownLanguageError
from esolangs.registry._catalog import Catalog, get_catalog
from esolangs.registry._language import LanguageDeclaration
from esolangs.registry._slug import SUGGESTION_CUTOFF, canonical_id
from esolangs.runtime._definition import SourceKind
from esolangs.runtime._validate import _has_backing_type

__all__ = [
    "BY_BOOLEAN",
    "CATALOG",
    "INTERPRETERS",
    "LANGUAGES",
    "SUGGESTION_CUTOFF",
    "Catalog",
    "Generator",
    "LanguageDeclaration",
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

    BY_BOOLEAN: Mapping[str, LanguageDeclaration]
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
            "BY_BOOLEAN": catalog._by_boolean,  # noqa: SLF001
            "INTERPRETERS": catalog._interpreters,  # noqa: SLF001
        }[name]
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(__all__)


def example_stems(*, catalog: Catalog | None = None) -> Mapping[str, str]:
    """Return example stems from declarations without importing example builders."""
    return get_catalog(catalog)._example_stems  # noqa: SLF001 - catalog-owned index


def _reads_inputs(language_id: str) -> TemplateError:
    """Refuse a template operation on a language that reads its inputs."""
    return TemplateError(f"{language_id} reads its inputs rather than embedding them")


def template_char(language_id: str, *, catalog: Catalog | None = None) -> str | None:
    """Return the character ``language_id``'s templates spell inputs with."""
    _, template = _template(language_id, catalog=catalog)
    return None if template is None else template.char


def _template(
    language_id: str, *, catalog: Catalog | None = None
) -> tuple[str, TemplateSpec | None]:
    """Normalize an identifier and look up its declared input bindings."""
    catalog = get_catalog(catalog)
    if not _has_backing_type(language_id, str):
        raise ArgumentError(
            f"a language identifier must be a string, got {type(language_id).__name__}"
        )
    identifier = str.__str__(language_id)
    name = catalog._by_id.get(identifier)  # noqa: SLF001
    if name is None:
        return identifier, None
    backend = catalog.languages[name].backend
    return identifier, None if backend is None else backend.template


def template_setters(
    language_id: str, template: str, n: int, *, catalog: Catalog | None = None
) -> Setters:
    """Return the ``(zero, one)`` pairs ``template`` fills its ``n`` inputs with.

    ``template`` is the generator's own output (slots, before rendering)
    or the rendered run form -- the setters read what they need from it,
    which for the two-route generators is the route's prefix.
    """
    identifier, spec = _template(language_id, catalog=catalog)
    if spec is None:
        raise TemplateError(f"unknown language: {identifier}")
    return spec.bindings(template, n)


def render_template(
    language_id: str,
    slots: str,
    n: int,
    *,
    catalog: Catalog | None = None,
) -> tuple[str, str, Setters]:
    """Return ``(text, char, setters)`` for a generator's laid-out slots."""
    identifier, spec = _template(language_id, catalog=catalog)
    if spec is None:
        raise _reads_inputs(identifier)
    return slots, spec.char, spec.bindings(slots, n)


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
    if not _has_backing_type(name, str):
        raise ArgumentError(
            f"a language name must be a string, got {type(name).__name__}"
        )
    try:
        slug = quote(str.__str__(name).replace(" ", "_"), safe=_WIKI_SAFE)
    except UnicodeEncodeError as error:
        raise ArgumentError("language names must be valid UTF-8 text") from error
    return f"https://esolangs.org/wiki/{slug}"


def resolve(name: str, *, catalog: Catalog | None = None) -> str:
    """Resolve a language name within the selected immutable catalog."""
    return get_catalog(catalog).resolve(name)
