"""Registry of language metadata, used by the API, tools, and tests."""

from __future__ import annotations

import difflib
import re
import unicodedata
from collections import Counter
from functools import cache
from urllib.parse import quote

from esolangs.exceptions import TemplateError, UnknownLanguageError
from esolangs.generation.helpers import Setters, mark_runs, unmark
from esolangs.generation.wrap import wrap_program
from esolangs.registry._backend import Generator, TemplateSpec
from esolangs.registry._language import Language
from esolangs.registry._slug import SUGGESTION_CUTOFF, canonical_id
from esolangs.registry._table import LANGUAGES
from esolangs.runtime._definition import SourceKind

__all__ = [
    "BY_BOOLEAN",
    "INTERPRETERS",
    "LANGUAGES",
    "RUNNERS",
    "SUGGESTION_CUTOFF",
    "Generator",
    "Language",
    "SourceKind",
    "canonical_id",
    "example_stems",
    "parameterized_ids",
    "render_template",
    "resolve",
    "template_char",
    "template_setters",
    "wiki_url",
]


# Generator function name -> Language, so tests can look one up by its
# function name.  A twin keyed by the removed text generators' names made a
# sweep skip sixteen boolean generators silently, which is how one
# language's input count survived; one map leaves no wrong pick.
BY_BOOLEAN: dict[str, Language] = {
    lang.id: lang for lang in LANGUAGES.values() if lang.backend is not None
}

# Display name -> (interpreter module, split lines).
RUNNERS: dict[str, tuple[str, bool]] = {
    name: (lang.runtime.interpreter, lang.runtime.split)
    for name, lang in LANGUAGES.items()
    if lang.runtime.interpreter
}


INTERPRETERS = {
    name: f"esolangs.languages.{lang.id}.interpreter"
    for name, lang in LANGUAGES.items()
    if lang.runtime.interpreter is not None
}


@cache
def example_stems() -> dict[str, str]:
    """Return example stems from declarations without importing example builders."""
    stems = {}
    for lang in LANGUAGES.values():
        if lang.backend is None or lang.runtime.interpreter is None:
            continue
        # Windows rejects punctuation such as `?`; slash names also need ids.
        stem = lang.name.lower().replace(" ", "-")
        stems[lang.id] = (
            lang.id.replace("_", "-") if re.search(r'[/*()+<>:"\\|?]', stem) else stem
        )
    return stems


def _reads_inputs(language_id: str) -> TemplateError:
    """Refuse a template operation on a language that reads its inputs."""
    return TemplateError(f"{language_id} reads its inputs rather than embedding them")


def template_char(language_id: str) -> str | None:
    """Return the character ``language_id``'s templates spell inputs with."""
    template = _template(language_id)
    return None if template is None else template.char


def _template(language_id: str) -> TemplateSpec | None:
    """Return a backend's input binding declaration using the existing id index."""
    name = _BY_ID.get(language_id)
    if name is None:
        return None
    backend = LANGUAGES[name].backend
    return None if backend is None else backend.template


def template_setters(language_id: str, template: str, n: int) -> Setters:
    """Return the ``(zero, one)`` pairs ``template`` fills its ``n`` inputs with.

    ``template`` is the generator's own output (slots, before rendering)
    or the rendered run form -- the setters read what they need from it,
    which for the two-route generators is the route's prefix.
    """
    spec = _template(language_id)
    if spec is None:
        raise TemplateError(f"unknown language: {language_id}")
    return spec.bindings(template, n)


def render_template(
    language_id: str,
    slots: str,
    n: int,
    width: int | None = None,
) -> tuple[str, str, Setters]:
    """Return the public template for a generator's slot-marked output.

    ``(text, char, setters)``: each input a run of the language's character
    as long as its setter.  With a ``width`` each input is marked and the
    wrapper breaks every run of the same length the same way, so the wrapped
    template is the wrapped form of every program it fills to.
    """
    char = template_char(language_id)
    if char is None:
        raise _reads_inputs(language_id)
    setters = template_setters(language_id, slots, n)
    if width is None:
        return slots, char, setters
    wrapped = wrap_program(mark_runs(slots, char, setters), language_id, width)
    return unmark(wrapped, char, n), char, setters


def parameterized_ids() -> frozenset[str]:
    """Return the canonical ids whose boolean generator emits a template."""
    return frozenset(lang.id for lang in LANGUAGES.values() if lang.parameterized)


# Canonical id -> display name, the index :func:`resolve` matches against.
_BY_ID: dict[str, str] = {lang.id: name for name, lang in LANGUAGES.items()}
# Casefolded display names and aliases, for names the slug rule cannot reach
# (a display name that slugs to another language's id).
_BY_FOLDED: dict[str, str] = {
    spelling.casefold(): name
    for name, lang in LANGUAGES.items()
    for spelling in (name, *lang.aliases)
}


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


def _symbols(*names: str) -> Counter[str]:
    """Count the characters a slug drops that are not separators."""
    counts: Counter[str] = Counter()
    for name in names:
        counts |= Counter(c for c in name if not (c.isalnum() or _separator(c)))
    return counts


def _separator(c: str) -> bool:
    # Whitespace and every dash: ``'\tfor_thorn\n'``, ``'Super\xa0SNUSP'`` and
    # ``'6\u20135'`` resolved before the symbol rule and must still.
    return c.isspace() or c == "_" or unicodedata.category(c) == "Pd"


def resolve(name: str) -> str:
    """Return the registered display name matching ``name``.

    An exact hit wins; otherwise :func:`canonical_id` makes the lookup case-
    and punctuation-insensitive: ``Brainfuck``, ``brainfuck`` and ``BRAINFUCK``
    all reach the registered ``brainfuck``.  Display names mix conventions, so
    callers cannot guess the spelling.  Only punctuation the name itself has
    may be dropped: ``Piet++`` and ``Brainfuck++`` are other wiki languages,
    and slugging them onto Piet and brainfuck ran the wrong one.  A miss raises
    :class:`UnknownLanguageError` naming the closest registered spellings.
    """
    if not isinstance(name, str):
        # Before ``canonical_id`` touches it: a ``None`` name would otherwise
        # escape as ``'NoneType' object has no attribute 'replace'`` from
        # inside the API.
        raise UnknownLanguageError(
            f"expected a language name, got {type(name).__name__}"
        )
    if name in LANGUAGES:
        return name
    match = _BY_FOLDED.get(name.strip().casefold())
    if match is not None:
        return match
    match = _BY_ID.get(canonical_id(name))
    if match is not None:
        own = _symbols(match, *LANGUAGES[match].aliases)
        if not _symbols(name) - own:
            return match
    close = difflib.get_close_matches(
        canonical_id(name), _BY_ID, n=2, cutoff=SUGGESTION_CUTOFF
    )
    if not close:
        # A head of a long name is too far for difflib: "lol" scores 0.18
        # against lol_waht_i_cant_edit_talk_pages.  Suggest, never resolve:
        # a head unique today turns ambiguous when a language is added.
        head = canonical_id(name).replace("_", "")
        starts = [i for i in _BY_ID if i.replace("_", "").startswith(head)]
        close = starts if len(head) >= 3 and len(starts) <= 2 else []
    raise UnknownLanguageError(name, suggestions=tuple(_BY_ID[c] for c in close))
