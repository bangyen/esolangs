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

from esolangs import generate
from esolangs.interpreters.io import IO
from esolangs.registry import LANGUAGES
from esolangs.tools.wrap import (
    DEFAULT_WIDTH,
    WRAPPERS,
    wrap_chars,
    wrap_program,
    wrap_space_delimited,
    wrap_tokens,
)

TEXT = "Hello, World!"

# Languages that must never be wrapped, and why.  Not a restatement of the
# implementation: each was verified to break (or to be meaningless) when
# newlines are inserted, so the table is the record of that finding.
UNWRAPPABLE = {
    "nocomment": "a newline is an unrecognized command, a load error",
    "wii2d": "2D: newlines separate rows",
    "dig": "2D: newlines separate rows",
    "clockwise": "2D: newlines separate rows",
    "laserfuck": "2D: newlines separate rows",
    "streetcode": "2D: newlines separate rows",
}

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
        if len(program) > 40:
            assert "\n" in generate(name, TEXT * repeat, 40)
            return
    pytest.fail(f"{name} never produced a program longer than 40 characters")


@pytest.mark.parametrize("name", sorted(UNWRAPPABLE))
def test_unwrappable_languages_are_untouched(name: str) -> None:
    """A language that cannot take newlines ignores the width."""
    language = next(lang for lang in LANGUAGES.values() if lang.id == name)
    assert language.id not in WRAPPERS, UNWRAPPABLE[name]
    if language.generator:
        assert generate(language.name, TEXT, 40) == generate(language.name, TEXT)


@pytest.mark.parametrize("name", WRAPPED)
def test_no_width_is_unchanged(name: str) -> None:
    """Omitting the width reproduces exactly what the generator always gave.

    This is what keeps the committed examples byte-identical: the sync
    tests in ``tests/test_examples.py`` call the generators with no width.
    """
    lang = LANGUAGES[name]
    assert lang.generator is not None
    assert generate(name, TEXT) == lang.generator(TEXT)


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
