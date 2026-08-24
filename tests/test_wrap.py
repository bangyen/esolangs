"""Wrapping a generated program must not change what it does.

The generators can emit a program wrapped to a readable width
(:func:`esolangs.generate` takes a ``width``).  The wrap is only safe if it
breaks between whole tokens, so the tests here run the *wrapped* program
through its interpreter and compare the output against the unwrapped one --
a wrap that split a token would still look plausible on screen but print
something else, which is exactly the failure a character-count wrap makes.

The exclusions are asserted too: a language whose newlines are semantic
must come back unwrapped rather than subtly broken.
"""

import importlib
import io
from contextlib import redirect_stdout, suppress

import pytest

from esolangs import generate, run
from esolangs.interpreters.io import IO
from esolangs.registry import LANGUAGES
from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES as BOOLEAN_GENERATED
from esolangs.tools.wrap import (
    DEFAULT_WIDTH,
    MULTILINE,
    WRAPPERS,
    wrap_chars,
    wrap_program,
    wrap_space_delimited,
    wrap_tokens,
)

TEXT = "Hello, World!"

# Languages that must never be *reflowed*, and why.  Not a restatement of
# the implementation: each was verified to break (or to be meaningless) when
# newlines are inserted, so the table is the record of that finding.
#
# Clockwise, Streetcode and WII2D are deliberately absent.  Their newlines
# are semantic too, so wrap_program must not touch them either -- but each
# honours a width by *laying its program out* to fit (a ring, a
# boustrophedon corridor, a folded instruction line) rather than by ignoring
# it, so they are covered by the generators' own tests in
# tests/tools/test_generate.py instead.
UNWRAPPABLE = {
    "nocomment": "a newline is an unrecognized command, a load error",
    "dig": "2D: newlines separate rows",
}

# LaserFuck is 2D too, and wrap_program must not touch it either -- but it
# honours a width itself: the loop layout is tied to the beam's track and
# cannot fold, so a loop program wider than the width is re-emitted as the
# (foldable) linear form.  Hence it belongs with Clockwise and the others
# above rather than in UNWRAPPABLE.
WIDTH_HONOURING = {"laserfuck": "falls back to the foldable linear form"}

WRAPPED = sorted(
    name
    for name, lang in LANGUAGES.items()
    if lang.generator and lang.interpreter and lang.id in WRAPPERS
)


def _replaces_a_space(name: str) -> bool:
    """Whether ``name``'s wrapper breaks at a space rather than between commands.

    The space-delimited languages already separate their tokens with a
    space, and the wrap puts the newline in that space's place; the
    character and fixed-token wrappers insert a newline where there was no
    separator at all.  Undoing the wrap therefore differs between the two.
    """
    return WRAPPERS[LANGUAGES[name].id] is wrap_space_delimited


def _run(name: str, program: str) -> str:
    """Run ``program`` through ``name``'s interpreter and return its stdout."""
    lang = LANGUAGES[name]
    assert lang.interpreter is not None
    run = importlib.import_module("esolangs.interpreters." + lang.interpreter).run
    argument = program.splitlines() if lang.split else program
    buffer = io.StringIO()
    with redirect_stdout(buffer), suppress(SystemExit):
        run(argument, io=IO(), **dict(lang.kwargs))
    return buffer.getvalue()


@pytest.mark.parametrize("name", WRAPPED)
@pytest.mark.parametrize("width", [40, DEFAULT_WIDTH])
def test_wrapped_program_prints_the_same(name: str, width: int) -> None:
    """A wrapped program prints exactly what the unwrapped one prints."""
    assert _run(name, generate(name, TEXT, width)) == _run(name, generate(name, TEXT))


@pytest.mark.parametrize("name", WRAPPED)
@pytest.mark.parametrize("width", [40, DEFAULT_WIDTH])
def test_wrapping_only_breaks_between_tokens(name: str, width: int) -> None:
    """Wrapping preserves the token sequence exactly.

    A newline either replaces a separator the program already had or is
    inserted between two adjacent commands, so splitting on whitespace
    recovers the original token sequence.  No command is dropped,
    reordered, or split -- the corruption a character-count wrap causes in
    the multi-character-token languages.
    """
    plain = generate(name, TEXT)
    wrapped = generate(name, TEXT, width)
    if wrapped == plain:
        # A program the generator already emits multi-line is left alone
        # (BFStack and Suffolk here); there is nothing to undo.
        return
    # Deleting the inserted newlines must recover the original exactly.
    # The space-delimited wrappers put the newline *where a space was*, so
    # there the newline turns back into that space; every other wrapper
    # inserts the newline between two adjacent commands, so it just goes
    # away.  Either way no command may be dropped, reordered, or split.
    restored = wrapped.replace("\n", " ") if _replaces_a_space(name) else wrapped
    assert restored.replace("\n", "") == plain


@pytest.mark.parametrize("name", WRAPPED)
def test_wrapping_respects_the_width(name: str) -> None:
    """No line exceeds the width, unless a single token already does.

    Polynomial's big-integer coefficients are longer than 80 characters and
    cannot be broken without changing the number, so such a token gets a
    line of its own rather than being split.
    """
    wrapped = generate(name, TEXT, DEFAULT_WIDTH)
    for line in wrapped.split("\n"):
        longest_token = max((len(t) for t in line.split()), default=0)
        assert len(line) <= max(DEFAULT_WIDTH, longest_token)


@pytest.mark.parametrize("name", WRAPPED)
def test_every_wrapper_actually_fires(name: str) -> None:
    """Every language in the table really does wrap, given enough program.

    Guards against a wrapper entry that silently never fires -- a token
    pattern that fails to tile returns the program unchanged by design,
    which would make the round-trip tests above pass vacuously.  The text
    grows until the program is long enough to need a break, since the
    terser languages emit well under a line for a short text (and Factor,
    whose program is one huge integer, cannot take a long one at all).
    """
    for repeat in (1, 2, 4, 8):
        program = generate(name, TEXT * repeat)
        if "\n" not in program and len(program) > 40:
            assert "\n" in generate(name, TEXT * repeat, 40)
            return
    # BFStack and Suffolk emit their hello-world programs already
    # multi-line, so the text generator can never exercise their wrapper;
    # their single-line *boolean* programs are what needs it.
    example = BOOLEAN_GENERATED.get(LANGUAGES[name].id)
    if example is not None:
        raw = example.build(width=None)
        # A language in MULTILINE arrives with structural newlines of its
        # own (Taglate's queue seed), so "did it wrap?" is not "is there a
        # newline?" -- it is whether wrapping added one and held the width.
        if LANGUAGES[name].id in MULTILINE:
            assert max(map(len, raw.split("\n"))) > 40, (
                f"{name}: boolean program too short to need a wrap"
            )
            wrapped = example.build(40)
            assert wrapped.count("\n") > raw.count("\n"), f"{name}: wrapper never fired"
            assert max(map(len, wrapped.split("\n"))) <= 40
            return
        assert "\n" not in raw, f"{name}: boolean program is already multi-line"
        assert len(raw) > 40, f"{name}: boolean program too short to need a wrap"
        assert "\n" in example.build(40)
        return
    pytest.fail(f"{name} never produced a single-line program longer than 40 chars")


@pytest.mark.parametrize("name", sorted(UNWRAPPABLE))
def test_unwrappable_languages_are_untouched(name: str) -> None:
    """A language that cannot take newlines ignores the width."""
    language = next(lang for lang in LANGUAGES.values() if lang.id == name)
    assert language.id not in WRAPPERS, UNWRAPPABLE[name]
    if language.generator:
        assert generate(language.name, TEXT, 40) == generate(language.name, TEXT)


@pytest.mark.parametrize("name", sorted(WIDTH_HONOURING))
def test_width_honouring_languages_respect_the_width(name: str) -> None:
    """A generator that lays itself out really does fit the width given.

    ``wrap_program`` cannot help these -- their newlines are layout -- so
    the width has to be honoured by the generator, and omitting it still
    has to reproduce the compact form it always gave.
    """
    language = next(lang for lang in LANGUAGES.values() if lang.id == name)
    assert language.id not in WRAPPERS, WIDTH_HONOURING[name]
    unbounded = generate(language.name, TEXT)
    for width in (40, 80, 94):
        program = generate(language.name, TEXT, width)
        assert max(map(len, program.split("\n"))) <= width
        assert run(language.name, program) == TEXT
    # a width the compact form already fits leaves it exactly as it was
    wide = max(map(len, unbounded.split("\n")))
    assert generate(language.name, TEXT, wide) == unbounded


@pytest.mark.parametrize("name", WRAPPED)
def test_no_width_is_unchanged(name: str) -> None:
    """Omitting the width reproduces exactly what the generator always gave.

    This is what keeps the committed examples byte-identical: the sync
    tests in ``tests/test_examples.py`` call the generators with no width.
    """
    lang = LANGUAGES[name]
    assert lang.generator is not None
    assert generate(name, TEXT) == lang.generator(TEXT)


def test_clockwise_is_never_reflowed() -> None:
    """Clockwise honours a width by shaping, never by inserting newlines.

    Its grid rows are semantic, so ``wrap_program`` must leave it alone even
    though ``generate`` does respond to a width for it -- the width reaches
    the generator instead.
    """
    assert "clockwise" not in WRAPPERS
    grid = generate("Clockwise", TEXT)
    assert wrap_program(grid, "clockwise", 10) == grid


def test_clockwise_width_reaches_the_generator() -> None:
    """``generate`` bounds Clockwise's columns rather than ignoring the width."""
    narrow = generate("Clockwise", TEXT, 20)
    assert max(len(line) for line in narrow.split("\n")) <= 20
    assert _run("Clockwise", narrow) == TEXT


def test_zero_and_negative_widths_do_not_wrap() -> None:
    """A nonsensical width is a no-op rather than an error or a crash."""
    for width in (0, -1):
        assert wrap_program("a b c", "decleq", width) == "a b c"


def test_already_multiline_programs_are_left_alone() -> None:
    """A program that already has newlines is never re-wrapped."""
    program = "line one\nline two"
    assert wrap_program(program, "decleq", 4) == program


def test_wrap_tokens_refuses_a_pattern_that_does_not_tile() -> None:
    """A pattern that drops characters returns the program unwrapped.

    The guard matters because a partial match would otherwise silently
    delete commands while still producing a runnable-looking program.
    """
    assert wrap_tokens("aXbXc", 2, "[abc]") == "aXbXc"


def test_wrap_space_delimited_never_splits_a_token() -> None:
    """A token longer than the width gets its own line, unbroken."""
    wrapped = wrap_space_delimited("1 22 333333 4", 3)
    assert "333333" in wrapped.split("\n")
    assert wrapped.replace("\n", " ") == "1 22 333333 4"


def test_wrap_chars_breaks_anywhere() -> None:
    """The single-character families break at exactly the width."""
    assert wrap_chars("abcdef", 2) == "ab\ncd\nef"
