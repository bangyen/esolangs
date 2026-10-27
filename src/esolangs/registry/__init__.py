"""Registry of language metadata, used by the API, tools, and tests."""

from __future__ import annotations

import difflib
import unicodedata
from collections import Counter
from functools import cache
from typing import TYPE_CHECKING
from urllib.parse import quote

from esolangs.exceptions import TemplateError, UnknownLanguageError
from esolangs.generation.helpers import MOST_INPUTS, Setters, mark_runs, runs, unmark
from esolangs.generation.wrap import wrap_program
from esolangs.registry._slug import SUGGESTION_CUTOFF, canonical_id
from esolangs.registry._table import LANGUAGES, Generator, Language, SourceKind

if TYPE_CHECKING:
    from esolangs.generation.examples import BooleanExample


__all__ = [
    "BY_BOOLEAN",
    "GENERATORS",
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
    "recover_setters",
    "render_template",
    "resolve",
    "template_body",
    "template_char",
    "template_setters",
    "wiki_url",
]


# Generator function name -> Language, so tests can look one up by its
# function name.  A twin keyed by the removed text generators' names made a
# sweep skip sixteen boolean generators silently, which is how one
# language's input count survived; one map leaves no wrong pick.
BY_BOOLEAN: dict[str, Language] = {
    lang.boolean.__name__: lang
    for lang in LANGUAGES.values()
    if lang.boolean is not None
}

# Display name -> (interpreter module, split lines).
RUNNERS: dict[str, tuple[str, bool]] = {
    name: (lang.interpreter, lang.split)
    for name, lang in LANGUAGES.items()
    if lang.interpreter
}

# Public workflows select by capability.
GENERATORS = {
    name: generator
    for name, lang in LANGUAGES.items()
    if (generator := lang.boolean) is not None
}
INTERPRETERS = {
    name: f"esolangs.languages.{lang.id}.interpreter"
    for name, lang in LANGUAGES.items()
    if lang.interpreter is not None
}


@cache
def example_stems() -> dict[str, str]:
    """Return canonical id -> the example filename stem, per language.

    Stems are dash-separated display names, internal references are canonical
    IDs, and a few match neither by hand.  The map derives from the example
    table :meth:`~esolangs.generation.examples.BooleanExample.build` uses, so
    a mismatch is a missing key, not a silently empty example list (which once
    left a fifth of the registry reporting none).  The import is deferred
    because ``examples`` imports this module.
    """
    from esolangs.generation import examples as _examples

    return {
        example.language: stem for stem, example in _examples.BOOLEAN_EXAMPLES.items()
    }


@cache
def _examples_by_id() -> dict[str, BooleanExample]:
    """Return canonical id -> example, for the templates only."""
    from esolangs.generation import examples as _examples

    return {
        example.language: example
        for example in _examples.BOOLEAN_EXAMPLES.values()
        if example.setters is not None
    }


def _reads_inputs(language_id: str) -> TemplateError:
    """Refuse a template operation on a language that reads its inputs."""
    return TemplateError(f"{language_id} reads its inputs rather than embedding them")


def template_char(language_id: str) -> str | None:
    """Return the character ``language_id``'s templates spell inputs with."""
    example = _examples_by_id().get(language_id)
    return None if example is None else example.char


def _example(language_id: str) -> BooleanExample:
    """Return the template example of ``language_id``, or refuse."""
    example = _examples_by_id().get(language_id)
    if example is None:
        raise TemplateError(f"unknown language: {language_id}")
    return example


def template_body(language_id: str, text: str) -> str:
    """Return ``text`` without the header a template carries for its setters.

    A template is all program; no remaining language carries a header.
    """
    body = _example(language_id).body
    return text if body is None else body(text)


def template_setters(language_id: str, template: str, n: int) -> Setters:
    """Return the ``(zero, one)`` pairs ``template`` fills its ``n`` inputs with.

    ``template`` is the generator's own output (slots, before rendering)
    or the rendered run form -- the setters read what they need from it,
    which for the two-route generators is the route's prefix.
    """
    setters = _example(language_id).setters
    if setters is None:
        raise _reads_inputs(language_id)
    return setters(template, n)


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


def recover_setters(language_id: str, template: str) -> Setters:
    """Return the pairs a plain run-form ``template`` was rendered from.

    A template read back from a file carries no pairs, but the language's
    setters are a function of the input count alone (plus the text, for the
    header and route cases), and the runs' total length grows with the
    count -- every generator spells more with more inputs -- so the count
    is the one value at which the widths sum to what the text holds.  The
    runs are then checked against it like any other template.
    """
    char = template_char(language_id)
    if char is None:
        raise _reads_inputs(language_id)
    total = template.count(char)
    # Past MOST_INPUTS every generator is capped by its own table size.
    for n in range(1, MOST_INPUTS + 1):
        setters = template_setters(language_id, template, n)
        if sum(len(zero) for zero, _one in setters) != total:
            continue
        runs(template, char, setters)  # refuses a shape the widths do not fit
        return setters
    raise ValueError(
        f"no input count makes this text a {language_id} template: it has "
        f"{total} of {char!r}"
    )


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
    raise UnknownLanguageError(name, tuple(_BY_ID[c] for c in close))
