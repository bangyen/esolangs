"""Registry of language metadata, used by the API, tools, and tests."""

from __future__ import annotations

import difflib
from collections.abc import Callable
from functools import cache
from typing import TYPE_CHECKING
from urllib.parse import quote

from esolangs.exceptions import TemplateError, UnknownLanguageError
from esolangs.registry._slug import SUGGESTION_CUTOFF, canonical_id
from esolangs.registry._table import LANGUAGES, Generator, Language
from esolangs.tools.helpers import MOST_INPUTS, Setters

if TYPE_CHECKING:
    from esolangs.tools.examples import BooleanExample


__all__ = [
    "BY_BOOLEAN",
    "LANGUAGES",
    "RUNNERS",
    "SUGGESTION_CUTOFF",
    "Generator",
    "Language",
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
# function name (``six_five`` for "6-5").  A twin keyed by the removed text
# generators' names made a sweep skip sixteen boolean generators silently,
# which is how Jaune's input count survived; one map leaves no wrong pick.
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


@cache
def example_stems() -> dict[str, str]:
    """Return canonical id -> the ``examples/`` filename stem, per language.

    The stems are dash-separated display names (``a-painter-ant``); every
    internal reference is the underscored slug (``a_painter_ant``), and a few
    match neither by hand.  Deriving the map from the same example table
    :meth:`~esolangs.tools.examples.BooleanExample.build` uses keeps the two
    from drifting: a mismatch is a missing key, not a silently empty example
    list, which once left a fifth of the registry reporting none.  The import
    is deferred because ``examples`` imports this module.
    """
    from esolangs.tools import examples as _examples

    return {
        canonical_id(stem.replace("-", " ")): stem
        for stem in set(_examples.BOOLEAN_EXAMPLES) | set(_examples.HAND_WRITTEN)
    }


@cache
def _fills() -> dict[str, Callable[[str, list[int]], str]]:
    """Return canonical id -> the substitution that instantiates a template.

    A *parameterized* generator returns a program with one run of ``$`` per
    input instead of one that reads its inputs; each committed example
    already carries the substitution as its ``fill``, so this exposes the
    existing recipe rather than a second list.  Membership is derived, not
    written down: ``parameterized.__all__`` omits Home Row, whose generator
    emits the runs all the same, and the three hand-kept doc lists each
    named a different subset.  ``fill`` matches what the generators emit.
    """
    from esolangs.tools import examples as _examples

    return {
        canonical_id(stem.replace("-", " ")): example.fill
        for stem, example in _examples.BOOLEAN_EXAMPLES.items()
        if example.fill is not None
    }


def _examples_by_id() -> dict[str, BooleanExample]:
    from esolangs.tools import examples as _examples

    return {
        canonical_id(stem.replace("-", " ")): example
        for stem, example in _examples.BOOLEAN_EXAMPLES.items()
        if example.setters is not None
    }


def template_char(language_id: str) -> str | None:
    """Return the character ``language_id``'s templates spell inputs with."""
    example = _examples_by_id().get(language_id)
    return None if example is None else example.char


def template_body(language_id: str, text: str) -> str:
    """Return ``text`` without the header a template carries for its setters.

    A template is all program; no remaining language carries a header.
    """
    body = _examples_by_id()[language_id].body
    return text if body is None else body(text)


def template_setters(language_id: str, template: str, n: int) -> Setters:
    """Return the ``(zero, one)`` pairs ``template`` fills its ``n`` inputs with.

    ``template`` is the generator's own output (slots, before rendering)
    or the rendered run form -- the setters read what they need from it,
    which for the two-route generators is the route's prefix.
    """
    setters = _examples_by_id()[language_id].setters
    if setters is None:  # pragma: no cover -- _examples_by_id keeps only setters
        raise TemplateError(
            f"{language_id} reads its inputs rather than embedding them"
        )
    return setters(template, n)


def render_template(
    language_id: str, slots: str, n: int, width: int | None = None
) -> tuple[str, str, Setters]:
    """Return the public template for a generator's slot-marked output.

    ``(text, char, setters)``: each input a run of the language's character
    as long as its setter.  With a ``width`` each input is marked and the
    wrapper breaks every run of the same length the same way, so the wrapped
    template is the wrapped form of every program it fills to.
    """
    from esolangs.tools.helpers import render, unmark
    from esolangs.tools.wrap import wrap_program

    char = template_char(language_id)
    if char is None:
        raise TemplateError(
            f"{language_id} reads its inputs rather than embedding them"
        )
    setters = template_setters(language_id, slots, n)
    if width is None:
        return render(slots, char, setters), char, setters
    wrapped = wrap_program(render(slots, None, setters), language_id, width)
    return unmark(wrapped, char, n), char, setters


#: The most inputs :func:`recover_setters` searches for; past this every
#: generator is capped by its own table size.
_MOST_INPUTS = MOST_INPUTS


def recover_setters(language_id: str, template: str) -> Setters:
    """Return the pairs a plain run-form ``template`` was rendered from.

    A template read back from a file carries no pairs, but the language's
    setters are a function of the input count alone (plus the text, for the
    header and route cases), and the runs' total length grows with the
    count -- every generator spells more with more inputs -- so the count
    is the one value at which the widths sum to what the text holds.  The
    runs are then checked against it like any other template.
    """
    from esolangs.tools.helpers import runs

    char = template_char(language_id)
    if char is None:
        raise TemplateError(
            f"{language_id} reads its inputs rather than embedding them"
        )
    total = template.count(char)
    for n in range(1, _MOST_INPUTS + 1):
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
    return frozenset(_fills())


# Canonical id -> display name, the index :func:`resolve` matches against.
_BY_ID: dict[str, str] = {lang.id: name for name, lang in LANGUAGES.items()}


#: Characters a wiki slug may keep: RFC 3986's unreserved set and sub-delims,
#: so parentheses, ``*``, ``~`` and ``-`` stay readable.  ``%`` is the escape
#: character itself and ``^`` is in neither set, so a name carrying either
#: went out escaped and the wiki answered 400.  Non-ASCII is escaped too:
#: ``Forþ`` as raw bytes is served by a browser and refused by a strict one.
_WIKI_SAFE = "_-.~()*!'+,;=:@&$"


def wiki_url(name: str) -> str:
    """Return the esolangs.org page for a language's display name.

    One function because there were two constructions -- :func:`describe`
    built the URL inline and ``scripts/generate.py docs`` built it
    again for the README -- so the same broken link shipped in both, and a
    fix to either would have left the other wrong.
    """
    slug = quote(name.replace(" ", "_"), safe=_WIKI_SAFE)
    return f"https://esolangs.org/wiki/{slug}"


def resolve(name: str) -> str:
    """Return the registered display name matching ``name``.

    An exact hit wins; otherwise the name is matched by :func:`canonical_id`,
    which makes the lookup case- and punctuation-insensitive: ``Brainfuck``,
    ``brainfuck`` and ``BRAINFUCK`` all reach the registered ``brainfuck``.
    The display names mix conventions (``brainfuck``, ``Suffolk``, ``bit~``),
    so a caller cannot guess the spelling, and "unknown language" for a name
    plainly in ``esolangs list`` is the wrong answer.  A miss raises
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
    match = _BY_ID.get(canonical_id(name))
    if match is not None:
        return match
    close = difflib.get_close_matches(
        canonical_id(name), _BY_ID, n=2, cutoff=SUGGESTION_CUTOFF
    )
    raise UnknownLanguageError(name, tuple(_BY_ID[c] for c in close))
