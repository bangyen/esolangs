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


# Generator function name -> Language, so tests can look a generator up by
# the name of its function (e.g. ``six_five`` for "6-5").
#
# This used to have a twin keyed by the *text* generator's name, and a sweep
# written over that twin silently skipped every boolean-only language rather
# than failing.  That is how Jaune's table-dependent input count survived:
# sixteen boolean generators were invisible to the read-count contract test.
# Keying only by ``boolean`` leaves nothing to pick the wrong map from.
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

    The stems are dash-separated display names (``a-painter-ant``), while
    every internal reference is the underscored :func:`canonical_id` slug
    (``a_painter_ant``), and a few match neither by hand (``6-5``).
    Deriving the map from the example table the
    same way :meth:`~esolangs.tools.examples.BooleanExample.build`
    does keeps the two spellings from drifting: a stem with no language, or
    a language with no stem, shows up as a missing key rather than as a
    silently empty example list, which is how a fifth of the registry came
    to report none.

    The import is deferred because ``examples`` imports this module; the
    map is wanted only when someone asks for a description, so paying for
    it then costs nothing at import time.
    """
    from esolangs.tools import examples as _examples

    return {
        canonical_id(stem.replace("-", " ")): stem
        for stem in set(_examples.BOOLEAN_EXAMPLES) | set(_examples.HAND_WRITTEN)
    }


@cache
def _fills() -> dict[str, Callable[[str, list[int]], str]]:
    """Return canonical id -> the substitution that instantiates a template.

    A *parameterized* generator returns a program with one run of ``$``
    per input rather than one that reads its inputs, and the runs are filled with that
    language's own code for setting an input.  Each committed example
    already carries that substitution as its ``fill``, so this is the
    existing recipe exposed rather than a second list to keep in step.

    Membership here is the definition of "parameterized" used everywhere in
    the package, and it is derived rather than written down for a measured
    reason: the same set taken from ``parameterized.__all__`` omits Home
    Row, whose generator emits the runs all the same, and the three
    hand-kept lists in the docs each named a different subset.  ``fill`` is
    the only spelling that matches what the generators actually emit --
    the count it returns is checked against the runs over every one.
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

    ``(text, char, setters)``: the text, with each input a run of the
    language's character as long as input ``i``'s setter, the
    character, and the pairs.  With a ``width`` the text is wrapped first,
    each input spelled as its own mark so the wrapper keeps every run whole
    and apart from its neighbour; a run is its setter's exact length, so
    the wrapped template is the wrapped form of every program it fills to
    -- the same breaks on every row.
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


#: Characters a wiki slug may keep as themselves.
#:
#: RFC 3986 lets a path segment carry the unreserved set and the sub-delims,
#: so parentheses, ``*``, ``~`` and ``-`` stay readable -- ``CV(N)(C)`` is a
#: better link than ``CV%28N%29%28C%29`` and both resolve.  What is *not*
#: here is the point: ``%`` is the escape character itself and ``^`` is in
#: neither set, so a name carrying either went out percent-escaped and the
#: wiki answered 400.  Non-ASCII is escaped too: ``Forþ`` as raw bytes is
#: served by a browser and refused by a strict client.
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

    An exact hit wins.  Otherwise the name is matched by its
    :func:`canonical_id`, which makes the lookup case- and
    punctuation-insensitive: ``Brainfuck``, ``brainfuck`` and ``BRAINFUCK``
    all reach the one registered ``brainfuck``.  That the display names mix
    conventions (``brainfuck``, ``Suffolk``, ``bit~``) is exactly why -- a
    caller cannot guess which one a given language follows, and being told
    "unknown language" for a name that is plainly in ``esolangs list`` is
    the wrong answer to a question of spelling.

    A name matching nothing raises :class:`UnknownLanguageError` naming the
    closest registered spellings.
    """
    if not isinstance(name, str):
        # Checked before ``canonical_id`` touches it, which would otherwise
        # answer a ``None`` language with ``'NoneType' object has no
        # attribute 'replace'`` -- the one wrong-type argument in the API
        # that escaped as an internal AttributeError.
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
