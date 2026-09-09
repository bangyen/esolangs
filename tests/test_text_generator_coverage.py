"""Every language that can print text has a text generator.

The companion to ``tests/test_limitations_doc.py``.  That test pins the
registry against the prose table in ``docs/limitations.md``, so the two
cannot drift -- but both sides of it are a *roster*: a language is exempt
because it is written down as exempt.  A roster answers "is this list
current", never "should this language have been on it".

This asks the second question.  ``Language.alphabet`` declares what a
language's output channel can spell, and the exemption is derived from
that: a language may lack a text generator only when its output cannot
carry one.  Adding a language that prints text and forgetting its
generator fails here, with no list to update, because ``alphabet``
defaults to ``"bytes"`` -- the failing direction is the default one.

``io`` is the second half, and it is a fact about the language's *spec*
rather than about this repo's interpreter.  Five languages here define no
I/O at all -- Back, Bitdeque, Minsky Swap, RAM0 and A Painter Ant -- and
their interpreters dump final state when the program ends precisely
*because* of that: the dump is the repo's convention for reporting
something from a language that cannot report anything itself, so its
format is the repo's choice and not the spec's.  Each of those
interpreters says so in its module docstring.

Recording the dump as though it were the language's own output mechanism
inverts that, and makes a language read as having a channel when what it
has is a workaround for lacking one.
"""

import pytest

from esolangs.registry import LANGUAGES, Language

# The alphabets that excuse a missing text generator, and what each claims.
# Spelled out here so a failure message can say *why* a language was
# excused rather than only that it was.
_EXEMPT = {
    "none": "defines no I/O and dumps nothing, so nothing reaches the caller",
    "numbers": "has a numeric or binary output alphabet",
    "shaped": "cannot spell an arbitrary text through its shaped output",
}


def _named() -> list[tuple[str, Language]]:
    return sorted(LANGUAGES.items())


_IDS = lambda v: v if isinstance(v, str) else ""  # noqa: E731


@pytest.mark.parametrize(("name", "lang"), _named(), ids=_IDS)
def test_a_text_printing_language_has_a_text_generator(
    name: str, lang: Language
) -> None:
    """A language whose output can spell text must have a text generator.

    The exemption is a property of the language, not membership of a list:
    it is read off ``alphabet``, which every entry carries and which
    defaults to ``"bytes"``.  A new language is therefore held to the
    generator requirement until somebody declares -- and, in
    ``docs/limitations.md``, explains -- why its output cannot carry one.
    """
    if lang.alphabet in _EXEMPT:
        return
    assert lang.alphabet == "bytes", (
        f"{name} declares alphabet={lang.alphabet!r}, which is not a known "
        f"category; add it to Alphabet and to _EXEMPT if it excuses a "
        f"missing text generator"
    )
    assert lang.text is not None, (
        f"{name} declares alphabet='bytes' -- its output can spell arbitrary "
        f"bytes -- but has no text generator.  Write one, or if its output "
        f"is in fact limited, declare the limit with alphabet= and record "
        f"why in docs/limitations.md's text-generator blockers table"
    )


@pytest.mark.parametrize(("name", "lang"), _named(), ids=_IDS)
def test_an_exempt_language_really_has_no_text_generator(
    name: str, lang: Language
) -> None:
    """An exemption that is not being used is a stale claim about a language.

    This is the direction that goes quietly wrong.  A language whose
    generator is written -- because the output turned out to be richer than
    the note said, which is how Back and A Painter Ant's boolean examples
    were unblocked -- keeps an ``alphabet`` that now understates it, and the
    understatement is invisible: every other check still passes.  Asserting
    the exemption is *load-bearing* is what dates it.
    """
    if lang.alphabet not in _EXEMPT:
        return
    assert lang.text is None, (
        f"{name} declares alphabet={lang.alphabet!r} -- it "
        f"{_EXEMPT[lang.alphabet]} -- but a text generator exists for it.  "
        f"The claim is stale: set alphabet='bytes' and drop its row from "
        f"docs/limitations.md"
    )


@pytest.mark.parametrize(("name", "lang"), _named(), ids=_IDS)
def test_reaching_nobody_leaves_no_alphabet(name: str, lang: Language) -> None:
    """``io`` and ``alphabet`` must agree about whether anything is emitted.

    The two are independent in general -- an interpreter-only dump can
    carry any alphabet, and a defined output command can still be numeric
    -- but not at the ends: a language nothing reaches the caller from has
    no alphabet to describe, and an alphabet needs something to carry it.
    Pinning that corner keeps a half-edited entry (``io`` changed,
    ``alphabet`` left behind) from reading as a coherent claim.
    """
    assert (lang.io == "none") == (lang.alphabet == "none"), (
        f"{name} declares io={lang.io!r} with alphabet={lang.alphabet!r} -- "
        f"a language with no I/O and no dump emits nothing, so both have to "
        f"say 'none' together"
    )


@pytest.mark.parametrize(("name", "lang"), _named(), ids=_IDS)
def test_a_silent_language_still_answers(name: str, lang: Language) -> None:
    """A language nothing reaches the caller from must answer by halting.

    ``io="none"`` is a real category, but the two languages in it are not
    alike, and only one of them is *unable* to dump.

    Point Break cannot: its spec leaves "whether it halts" as a program's
    only observable behavior, so there is no terminal state to report.

    ArrowQueue could -- its ``_State`` carries a queue that survives the
    halt -- but the dump would be worth little and cost a lot.  Of its two
    halt paths, the empty pop leaves the queue provably ``()``, so only a
    run that walks off the grid has anything to show; and ``_advance`` is
    pure and total precisely because "ArrowQueue has no I/O, so there is no
    effect to hoist out", so adding one would thread an effect parameter
    through the layer built to avoid it.  That is an interpreter design
    change, not something this test should force.

    What that costs is the usual way of checking an answer, so the
    termination convention carries it instead: the program halts for 0 and
    loops forever for 1 (``docs/walls.md`` licenses this only where a spec
    supplies a reliable verdict).  That convention is the language's whole
    interface, so a silent language without a boolean generator is
    unreachable -- nothing could observe it at all -- and that is the gap
    worth failing on, rather than the missing dump.
    """
    if lang.io != "none":
        return
    assert lang.boolean is not None, (
        f"{name} declares io='none' -- nothing it does reaches the caller -- "
        f"and has no boolean generator, so no program of it is observable.  "
        f"Either it answers by the termination convention, or its io= is "
        f"wrong and it emits something after all"
    )


def test_the_exempt_categories_are_all_used() -> None:
    """Every exemption category earns its place in :data:`Alphabet`.

    A category no language uses is an untested branch of the rule above:
    it would excuse a missing generator and nothing would ever exercise
    that.  Pinning use keeps the vocabulary honest -- a category that
    empties out should be deleted, not left as a hole to fall into.
    """
    used = {lang.alphabet for lang in LANGUAGES.values()}
    unused = sorted(set(_EXEMPT) - used)
    assert not unused, (
        f"these exemption categories are declared but unused: {unused} -- "
        f"delete them from Alphabet and _EXEMPT, or the rule has a branch "
        f"no language tests"
    )


def test_every_io_category_is_used() -> None:
    """The same, for ``io``.

    ``"interpreter_only"`` is the one worth pinning: it describes the five
    languages whose spec defines no I/O, and nothing else in the suite
    depends on it, so it could be quietly emptied by a recategorization and
    leave the vocabulary claiming a distinction the registry no longer
    draws.
    """
    used = {lang.io for lang in LANGUAGES.values()}
    missing = sorted({"defined", "interpreter_only", "none"} - used)
    assert not missing, (
        f"these I/O categories are declared but unused: {missing} -- delete "
        f"them from Io, or the distinction is not being drawn"
    )


def test_most_languages_are_held_to_the_requirement() -> None:
    """The requirement covers the bulk of the registry, not a remnant.

    The sweep above passes vacuously for any language it exempts, so a
    creeping exemption -- categories handed out until few languages are
    actually checked -- would empty the test out while it stayed green.
    Fifty-two of sixty-nine languages are held to it today; this floor
    fails long before that erodes to nothing.
    """
    held = [name for name, lang in LANGUAGES.items() if lang.alphabet == "bytes"]
    assert len(held) >= len(LANGUAGES) * 2 // 3, (
        f"only {len(held)} of {len(LANGUAGES)} languages are held to the "
        f"text-generator requirement -- exemptions have spread far enough "
        f"that this sweep checks little"
    )
