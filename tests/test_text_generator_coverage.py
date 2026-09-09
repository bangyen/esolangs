"""Every language that can print text has a text generator.

The companion to ``tests/test_limitations_doc.py``.  That test pins the
registry against the prose table in ``docs/limitations.md``, so the two
cannot drift -- but both sides of it are a *roster*: a language is exempt
because it is written down as exempt.  A roster answers "is this list
current", never "should this language have been on it".

This asks the second question.  ``Language.prints`` declares what a
language's output channel can spell, and the exemption is derived from
that: a language may lack a text generator only when its output is
``"nothing"``, ``"numbers"``, or ``"constrained"``.  Adding a language that
prints text and forgetting its generator fails here, with no list to
update, because ``prints`` defaults to ``"text"`` -- the failing direction
is the default one.
"""

import pytest

from esolangs.registry import LANGUAGES, Language

# The categories that excuse a missing text generator, and what each claims.
# Spelled out here so a failure message can say *why* a language was excused
# rather than only that it was.
_EXEMPT = {
    "nothing": "has no output command",
    "numbers": "has a numeric or binary output alphabet",
    "constrained": "cannot spell an arbitrary text through its shaped output",
}


def _named() -> list[tuple[str, Language]]:
    return sorted(LANGUAGES.items())


@pytest.mark.parametrize(("name", "lang"), _named(), ids=lambda v: v if isinstance(v, str) else "")
def test_a_text_printing_language_has_a_text_generator(name: str, lang: Language) -> None:
    """A language whose output can spell text must have a text generator.

    The exemption is a property of the language, not membership of a list:
    it is read off ``prints``, which every entry carries and which defaults
    to ``"text"``.  A new language is therefore held to the generator
    requirement until somebody declares -- and, in
    ``docs/limitations.md``, explains -- why its output cannot carry one.
    """
    if lang.prints in _EXEMPT:
        return
    assert lang.prints == "text", (
        f"{name} declares prints={lang.prints!r}, which is not a known "
        f"category; add it to Prints and to _EXEMPT if it excuses a "
        f"missing text generator"
    )
    assert lang.text is not None, (
        f"{name} declares prints='text' -- its output can spell arbitrary "
        f"bytes -- but has no text generator.  Write one, or if its output "
        f"is in fact limited, declare the limit with prints= and record why "
        f"in docs/limitations.md's text-generator blockers table"
    )


@pytest.mark.parametrize(("name", "lang"), _named(), ids=lambda v: v if isinstance(v, str) else "")
def test_an_exempt_language_really_has_no_text_generator(name: str, lang: Language) -> None:
    """An exemption that is not being used is a stale claim about a language.

    This is the direction that goes quietly wrong.  A language whose
    generator is written -- because the output turned out to be richer than
    the note said, which is how Back and A Painter Ant's boolean examples
    were unblocked -- keeps a ``prints`` that now understates it, and the
    understatement is invisible: every other check still passes.  Asserting
    the exemption is *load-bearing* is what dates it.
    """
    if lang.prints not in _EXEMPT:
        return
    assert lang.text is None, (
        f"{name} declares prints={lang.prints!r} -- it {_EXEMPT[lang.prints]} "
        f"-- but a text generator exists for it.  The claim is stale: set "
        f"prints='text' and drop its row from docs/limitations.md"
    )


def test_the_exempt_categories_are_all_used() -> None:
    """Every exemption category earns its place in :data:`Prints`.

    A category no language uses is an untested branch of the rule above:
    it would excuse a missing generator and nothing would ever exercise
    that. Pinning use keeps the vocabulary honest -- a category that
    empties out should be deleted, not left as a hole to fall into.
    """
    used = {lang.prints for lang in LANGUAGES.values()}
    unused = sorted(set(_EXEMPT) - used)
    assert not unused, (
        f"these exemption categories are declared but unused: {unused} -- "
        f"delete them from Prints and _EXEMPT, or the rule has a branch no "
        f"language tests"
    )


def test_most_languages_are_held_to_the_requirement() -> None:
    """The requirement covers the bulk of the registry, not a remnant.

    The sweep above passes vacuously for any language it exempts, so a
    creeping exemption -- categories handed out until few languages are
    actually checked -- would empty the test out while it stayed green.
    Fifty-two of sixty-nine languages are held to it today; this floor
    fails long before that erodes to nothing.
    """
    held = [name for name, lang in LANGUAGES.items() if lang.prints == "text"]
    assert len(held) >= len(LANGUAGES) * 2 // 3, (
        f"only {len(held)} of {len(LANGUAGES)} languages are held to the "
        f"text-generator requirement -- exemptions have spread far enough "
        f"that this sweep checks little"
    )
