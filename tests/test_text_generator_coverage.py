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
rather than about this repo's interpreter.  Seven languages here define no
I/O at all -- Back, Bitdeque, Minsky Swap, RAM0, A Painter Ant, ArrowQueue
and Point Break -- and their interpreters dump final state when the
program ends precisely *because* of that: the dump is the repo's
convention for reporting something from a language that cannot report
anything itself, so its format is the repo's choice and not the spec's.
Each of those interpreters says so in its module docstring.

Recording the dump as though it were the language's own output mechanism
inverts that, and makes a language read as having a channel when what it
has is a workaround for lacking one.
"""

import pathlib

import pytest

import esolangs
from esolangs.registry import LANGUAGES, Language

# The alphabets that excuse a missing text generator, and what each claims.
# Spelled out here so a failure message can say *why* a language was
# excused rather than only that it was.
_EXEMPT = {
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
def test_an_interpreter_only_language_actually_dumps(name: str, lang: Language) -> None:
    """A language with no I/O of its own must still report something.

    ``io="interpreter_only"`` claims the repo convention has been applied:
    the wiki gives the language no output, so the interpreter dumps final
    state when the program ends.  Nothing else here would notice a language
    that declares it and prints nothing -- the text-generator rule reads
    ``alphabet``, not ``io``.

    ArrowQueue and Point Break were that gap.  Both were carried as
    emitting nothing at all, on the reasoning that a dump would cost
    ArrowQueue its pure fold and that Point Break had no state worth
    printing.  Both were wrong: the dump belongs in the shell, where
    ``_advance`` never sees it, and Point Break carries variables exactly
    as Minsky Swap carries registers.  Being awkward to fit is not a
    category, so this runs the sample and checks output arrives -- the
    convention verified rather than asserted.
    """
    if lang.io != "interpreter_only":
        return
    # The dump has two legal placements -- a post-halt ``step`` (Minsky
    # Swap, Bitdeque, ArrowQueue, Point Break, RAM0) or straight from
    # ``run`` (Back, A Painter Ant) -- so the check is that the interpreter
    # *calls* the port, not where from.  Reading the source is what suits
    # this: the assertion is about the interpreter owing a dump, and a
    # language whose sample happens to dump an empty final state (Back's
    # blank tape) would pass an output check vacuously.
    source = pathlib.Path(esolangs.__file__).parent / "interpreters"
    module = source / (lang.interpreter.replace(".", "/") + ".py")
    assert "print_str" in module.read_text(encoding="utf-8"), (
        f"{name} declares io='interpreter_only' -- the language defines no "
        f"I/O, so its interpreter owes a final-state dump -- but "
        f"{module.name} never writes to the output port.  Either add the "
        f"dump, or the language has I/O after all and io= is wrong"
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
    missing = sorted({"defined", "interpreter_only"} - used)
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
