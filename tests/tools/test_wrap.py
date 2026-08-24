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
    _cell_width,
    _polynomial,
    _span,
    takes_width,
    wrap_chars,
    wrap_grid,
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
    space, and the wrap puts the newline in that space's place --
    Polynomial's wrapper included, since the space it keeps inside a
    ``sign term`` pair is one the program already had; the
    character and fixed-token wrappers insert a newline where there was no
    separator at all.  Undoing the wrap therefore differs between the two.
    """
    return WRAPPERS[LANGUAGES[name].id] in (wrap_space_delimited, _polynomial)


def _chunks_its_literal(name: str) -> bool:
    """Whether ``name``'s *text* generator lays itself out to the width.

    3x, Eval, Modulous and MyScript print through a literal, so their text
    programs cannot be reflowed at all -- a newline between the quotes is a
    character the program prints.  Their generators therefore take the width
    and split the text across several print statements, which builds a
    different program rather than inserting newlines into this one.  Their
    *boolean* programs carry no literal and are still reflowed by
    :data:`WRAPPERS`, so that is where the token-preserving invariant is
    checked for them.
    """
    generator = LANGUAGES[name].generator
    return generator is not None and takes_width(generator)


def _is_grid(name: str) -> bool:
    """Whether ``name``'s wrapper lays its tokens out as a padded grid.

    The grid wrapper right-aligns each token in a fixed-width cell, so the
    separator between two tokens is a *run* of spaces rather than the
    single one the other space-delimited wrappers leave.  Undoing that wrap
    means collapsing whitespace, not swapping one character for another.
    """
    return WRAPPERS[LANGUAGES[name].id] is wrap_grid


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
    if _chunks_its_literal(name):
        # The text generator builds a different program for the width rather
        # than reflowing one, so there are no inserted newlines to undo.  Its
        # boolean program is the one the wrapper still reflows, so check the
        # invariant there instead of losing the coverage.
        example = BOOLEAN_GENERATED.get(LANGUAGES[name].id)
        if example is None:
            return
        plain = example.build(width=None)
        wrapped = wrap_program(plain, LANGUAGES[name].id, width)
        assert wrapped.replace("\n", "") == plain
        return
    plain = generate(name, TEXT)
    wrapped = generate(name, TEXT, width)
    if wrapped == plain:
        # A program short enough to need no break is left alone; there is
        # nothing to undo.
        return
    # The grid wrapper pads each token to a cell and right-aligns it, so
    # the original text is not recoverable character for character -- the
    # padding is new whitespace.  What must survive is the token sequence
    # itself, which is the guarantee the character-for-character check is
    # standing in for everywhere else: no command dropped, reordered, or
    # split.  The interpreters split on whitespace runs, so a program with
    # the same token sequence is the same program.
    if _is_grid(name):
        assert wrapped.split() == plain.split()
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
    line of its own rather than being split.  Its unbreakable unit is the
    ``sign term`` pair rather than the bare term -- splitting the two is
    what stranded a lone ``+`` on a line -- so a line holding one runs two
    characters past the term's own length, and the allowance below follows
    the wrapper rather than the whitespace.
    """
    wrapped = generate(name, TEXT, DEFAULT_WIDTH)
    signed = WRAPPERS[LANGUAGES[name].id] is _polynomial
    for line in wrapped.split("\n"):
        tokens = line.split()
        longest_token = max((len(t) for t in tokens), default=0)
        if signed and tokens and tokens[0] in ("+", "-"):
            # The sign and the space that keeps it attached to its term.
            longest_token += 2
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
    # Some languages' hello-world programs are too terse to ever need a
    # break (Modulous and the other literal printers emit one statement),
    # so the text generator cannot exercise their wrapper; their longer
    # *boolean* programs are what needs it.
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
    tests in ``tests/scripts/test_examples.py`` call the generators with no width.
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


def test_polynomial_never_strands_a_sign_on_its_own_line() -> None:
    """The raggedness this wrapper exists to fix: a line that is just a sign.

    Polynomial's terms outgrow any sensible width, so the plain
    space-delimited wrapper put every term on a line of its own and every
    ``+``/``-`` between them on a line of its own too.
    """
    program = generate("Polynomial", TEXT, DEFAULT_WIDTH)
    assert "\n" in program
    assert not [line for line in program.split("\n") if line.strip() in ("+", "-")]


def test_polynomial_puts_one_term_on_each_line() -> None:
    """The layout: every line is exactly one term, sign included.

    A packed line would hold however many terms happened to fit, so its
    breaks would fall where the arithmetic landed rather than between two
    things a reader wants separated.
    """
    program = generate("Polynomial", TEXT, DEFAULT_WIDTH)
    lines = program.split("\n")
    # Line 1 is ``f(x) = <term>``; every other line is ``<sign> <term>``.
    assert lines[0].startswith("f(x) = ")
    # ``f(x)``, ``=`` and the unsigned leading term.
    assert len(lines[0].split()) == 3
    assert all(len(line.split()) == 2 for line in lines[1:])


def test_polynomial_continuation_lines_start_with_their_sign() -> None:
    """Every line but the first opens with the sign of its term."""
    program = generate("Polynomial", TEXT, DEFAULT_WIDTH)
    lines = program.split("\n")
    assert all(line.startswith(("+ ", "- ")) for line in lines[1:])


def test_polynomial_wrap_is_undone_by_swapping_newlines_for_spaces() -> None:
    """The wrap only moves separators, so the program is byte-identical."""
    plain = generate("Polynomial", TEXT)
    wrapped = generate("Polynomial", TEXT, DEFAULT_WIDTH)
    assert wrapped.replace("\n", " ") == plain


def test_polynomial_keeps_the_header_with_the_first_term() -> None:
    """``f(x)`` and ``=`` are not terms and do not get lines of their own."""
    assert _polynomial("f(x) = x^2 - 3x + 7", 80).split("\n")[0] == "f(x) = x^2"


def test_polynomial_layout_does_not_depend_on_the_width() -> None:
    """One term to a line whatever the width -- it is only the on/off switch.

    The terms of any interesting program outrun any width, so packing them
    to one would be a layout that changed with a number nobody chose.
    """
    program = generate("Polynomial", TEXT)
    assert _polynomial(program, 40) == _polynomial(program, 200)


def test_polynomial_keeps_an_oversized_term_with_its_sign() -> None:
    """A term wider than the width keeps its sign rather than shedding it.

    Splitting the pair to respect the width would put the sign back on a
    line by itself, which is the thing being fixed; an over-wide line is
    the honest outcome, as it is for any oversized token.
    """
    wrapped = _polynomial("f(x) = x^2 - 123456789x + 7", 12)
    assert "- 123456789x" in wrapped.split("\n")


def test_polynomial_leaves_a_trailing_sign_alone() -> None:
    """A sign with no term after it is kept rather than dropped."""
    assert _polynomial("f(x) = x +", 80) == "f(x) = x\n+"


def test_polynomial_keeps_a_sign_with_no_term_to_attach_to() -> None:
    """Two signs in a row: the first has no term, and is kept as a line.

    ``format_coeffs`` never emits that -- it collapses ``+ -`` into
    ``- `` -- so this is only the helper staying total.
    """
    assert _polynomial("f(x) = x + - 7", 80) == "f(x) = x\n+\n- 7"


def test_wrap_grid_right_aligns_into_columns() -> None:
    """Every token is right-aligned in a cell as wide as the widest one."""
    # Cell width 3, so 80 // 4 == 20 cells to a row at the default width.
    wrapped = wrap_grid("1 22 333 4", 80)
    assert wrapped == "  1  22 333   4"


def test_wrap_grid_columns_line_up_across_rows() -> None:
    """The point of the grid: column k starts at the same offset every row."""
    # Six 3-character tokens with room for three cells a row (11 columns
    # holds "aaa bbb ccc") puts two rows under each other.
    wrapped = wrap_grid("111 222 333 444 555 666", 11)
    rows = wrapped.split("\n")
    assert rows == ["111 222 333", "444 555 666"]
    starts = [[i for i, ch in enumerate(row) if ch != " "][::3] for row in rows]
    assert starts[0] == starts[1]


def test_wrap_grid_leaves_no_trailing_whitespace() -> None:
    """Right-aligning pads on the left, so no line ends in a space."""
    wrapped = wrap_grid("1 22 333 4 5 66", 12)
    for line in wrapped.split("\n"):
        assert line == line.rstrip()


def test_wrap_grid_preserves_the_token_sequence() -> None:
    """Padding is whitespace, so the tokens read back exactly."""
    program = "-1 321 3 -1 322 6 1000000000 0 0 48 49"
    assert wrap_grid(program, 40).split() == program.split()


def test_wrap_grid_sizes_cells_to_the_bulk_not_the_outlier() -> None:
    """A lone wide token does not pad every other cell out to its width.

    Decleq's boolean program is the real case: 321 tokens of three
    characters or fewer beside four ten-character jump sentinels.  Sizing
    every cell to the sentinel would leave the file mostly padding.
    """
    tokens = ["321"] * 20 + ["1000000000"]
    assert _cell_width(tokens) == 3
    # Without the outlier rule this would be 21 cells of width 10.
    wrapped = wrap_grid(" ".join(tokens), 80)
    assert wrapped.split("\n")[0] == " ".join(["321"] * 20)


def test_wrap_grid_spans_an_outlier_across_whole_cells() -> None:
    """A token too wide for one cell takes several, keeping the lattice.

    A 10-character token in a 3-character cell spans three cells (3 cells
    of 3 plus the 2 separators they absorb is 11 >= 10), so the tokens
    after it on the row still begin on a cell boundary -- which is the
    whole reason a wide token spans cells instead of just overflowing.
    """
    assert _span(10, 3) == 3
    wrapped = wrap_grid("111 222 1000000000 333 444", 80)
    assert wrapped == "111 222  1000000000 333 444"
    # "111 222 " is 8 columns, the span covers the next 11, so the token
    # after it starts at column 20 -- a multiple of the 4-column cell.
    assert wrapped.index("333") == 20
    assert wrapped.index("333") % 4 == 0


def test_wrap_grid_never_straddles_a_row_boundary() -> None:
    """A spanning token starts a new row rather than breaking across two."""
    # Cell width 2, so three cells (11 columns) to a row.  The 7-character
    # token needs three of them, which the first row cannot spare after
    # "11 22", so it opens the second row rather than breaking across both.
    wrapped = wrap_grid("11 22 1234567 33", 11)
    assert wrapped.split("\n") == ["11 22", " 1234567 33"]
    # The token stayed whole -- that is the guarantee being made here.
    assert "1234567" in wrapped.split("\n")[1]


def test_wrap_chars_breaks_anywhere() -> None:
    """The single-character families break at exactly the width."""
    assert wrap_chars("abcdef", 2) == "ab\ncd\nef"
