"""Wrapping a generated program must not change what it does.

The generators can emit a program wrapped to a readable width
(:func:`esolangs.generate` takes a ``width``).  The wrap is only safe if it
breaks between whole tokens, so the tests here run the *wrapped* program
through its interpreter and compare the output against the unwrapped one --
a wrap that split a token would still look plausible on screen but print
something else, which is exactly the failure a character-count wrap makes.

The sweep is driven by :data:`BOOLEAN_EXAMPLES`, which is the only thing
that produces programs now: each carries the inputs and the output its
table demands, so "does the wrapped program still compute it?" is asked
against the generator's own fixture rather than a stand-in.

The exclusions are asserted too: a language whose newlines are semantic
must come back unwrapped rather than subtly broken.
"""

import re

import pytest

from esolangs import generate, run
from esolangs.registry import LANGUAGES, canonical_id
from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES as BOOLEAN_GENERATED
from esolangs.tools.boolean.examples import BooleanExample
from esolangs.tools.wrap import (
    DEFAULT_WIDTH,
    MULTILINE,
    WRAPPERS,
    _bio,
    _bitdeque,
    _cell_width,
    _polynomial,
    _six_five,
    _span,
    _taglate,
    takes_width,
    wrap_chars,
    wrap_grid,
    wrap_program,
    wrap_space_delimited,
    wrap_tokens,
)

# A 2-input table (XOR), which every boolean generator can build.  Used
# where a test needs *a* program rather than the language's own example.
TABLE = "0110"

# A third width, narrower than any a reader would ask for, because a broken
# wrapper is not broken at every width.  Whether a break lands inside a
# multi-character token depends on where the width happens to put it, so a
# wrapper can be wrong and still pass at both conventional widths: Bitdeque
# answered 1 instead of 0 at 12 and 13 while 11, 14, 40 and 80 were all
# correct, and the three registered since (Lamfunc, RAM0, Jaune) each broke
# under wrap_chars at some width between 10 and 50 while passing at 80.
# Sweeping a dozen widths per language belongs in a scratch harness; one odd
# width in the suite is what keeps the class from coming back.
NARROW_WIDTH = 13

# Languages that must never be *reflowed*, and why.  Not a restatement of
# the implementation: each was verified to break (or to be meaningless) when
# newlines are inserted, so the table is the record of that finding.
#
# The four below NoComment were found the same way, by inserting a newline
# at every position of the language's own boolean program and running each
# one: none of the four has a single position that keeps the answer, so
# there is no token rule to find and no narrower width that would help.
# They are recorded because "we tried and it cannot be done" is worth as
# much as a wrapper, and because each is a long line that otherwise looks
# like an oversight -- CV(N)(C) reaches 1162 columns at n == 4.
UNWRAPPABLE = {
    "nocomment": "a newline is an unrecognized command, a load error",
    "grapheme": "every character must be A-Z, so a newline is a load error",
    "cvnc": "the source must syllabify and a newline is in no syllable",
    "fargo": "its newlines already separate statements",
    "minsky_swap": "its second line is absolute offsets into its first",
}

# These are 2D too, and wrap_program must not touch them either -- but each
# honours a width itself by *laying its program out* to fit rather than by
# ignoring it, so they belong here rather than in UNWRAPPABLE.  LaserFuck's
# loop layout is tied to the beam's track and cannot fold, so a loop program
# wider than the width is re-emitted as the (foldable) linear form.
#
# Derived from :func:`takes_width` rather than written out, for the reason
# ``esolangs.tools.boolean.BOOLEAN`` is derived from the registry: the
# hand-written table had drifted both ways.  It named Dig, which honours no
# width at all -- ``dig`` takes only a truth table, its ``width`` is the
# local constant ``len(_DIG_BRANCH)``, and the program it returns is
# identical whatever width is asked for, running 48 columns at ``n == 6``
# against a requested 40.  The 2-input table below is 20 columns wide, which
# is what let it pass.  And it omitted Streetcode, which really does take
# one.  A derived table cannot make either mistake.
WIDTH_HONOURING = sorted(
    lang.id
    for lang in LANGUAGES.values()
    if lang.boolean is not None and takes_width(lang.boolean)
)

# The boolean example for each language, keyed by the language id rather
# than the example's stem.  The two differ ("6-5" against ``six_five``), and
# a lookup by id against a stem-keyed table silently misses -- which is a
# skip, not a failure, so the sweep below would thin out without saying so.
EXAMPLE_BY_ID = {
    canonical_id(stem.replace("-", " ")): example
    for stem, example in BOOLEAN_GENERATED.items()
}

WRAPPED = sorted(
    name
    for name, lang in LANGUAGES.items()
    if lang.boolean
    and lang.interpreter
    and lang.id in WRAPPERS
    and lang.id in EXAMPLE_BY_ID
)


def _table(arity: int) -> str:
    """The parity (XOR) table on ``arity`` inputs.

    Parity, not an alternating string: ``0101`` is just "echo the last
    input", which every generator folds down to a program far shorter than
    its arity suggests.  Parity depends on all ``arity`` inputs, so the
    program grows with them -- which is what the sweeps below need.
    """
    return "".join(str(bin(row).count("1") & 1) for row in range(2**arity))


def _example(name: str) -> BooleanExample:
    """The boolean example for ``name``, which the sweep is driven by."""
    return EXAMPLE_BY_ID[LANGUAGES[name].id]


def _stdin(name: str) -> str:
    """The input lines ``name``'s example feeds its program."""
    return "".join(f"{line}\n" for line in _example(name).inputs)


def _replaces_a_space(name: str) -> bool:
    """Whether ``name``'s wrapper breaks at a space rather than between commands.

    The space-delimited languages already separate their tokens with a
    space, and the wrap puts the newline in that space's place --
    Polynomial's wrapper included, since the space it keeps inside a
    ``sign term`` pair is one the program already had; the
    character and fixed-token wrappers insert a newline where there was no
    separator at all.  Undoing the wrap therefore differs between the two.
    """
    return WRAPPERS[LANGUAGES[name].id] in (
        wrap_space_delimited,
        _polynomial,
        _bitdeque,
    )


def _is_grid(name: str) -> bool:
    """Whether ``name``'s wrapper lays its tokens out as a padded grid.

    The grid wrapper right-aligns each token in a fixed-width cell, so the
    separator between two tokens is a *run* of spaces rather than the
    single one the other space-delimited wrappers leave.  Undoing that wrap
    means collapsing whitespace, not swapping one character for another.
    """
    return WRAPPERS[LANGUAGES[name].id] is wrap_grid


def _run(name: str, program: str) -> str:
    """What ``program`` does under ``name``'s interpreter: output, or a raise.

    The example's inputs do not always drive its program to completion --
    some languages here dump final state rather than printing, and Suffolk
    reads past what its example scripts -- so a raise is a legitimate
    outcome to compare.  Returning it as a value rather than letting it
    escape keeps the wrapped/unwrapped comparison total: what must not
    change is the behaviour, including the failure.
    """
    try:
        return run(name, program, _stdin(name))
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


@pytest.mark.parametrize("name", WRAPPED)
@pytest.mark.parametrize("width", [NARROW_WIDTH, 40, DEFAULT_WIDTH])
def test_wrapped_program_prints_the_same(name: str, width: int) -> None:
    """A wrapped program behaves exactly as the unwrapped one behaves."""
    example = _example(name)
    assert _run(name, example.build(width)) == _run(name, example.build(width=None))


@pytest.mark.parametrize("name", WRAPPED)
@pytest.mark.parametrize("width", [NARROW_WIDTH, 40, DEFAULT_WIDTH])
def test_wrapping_only_breaks_between_tokens(name: str, width: int) -> None:
    """Wrapping preserves the token sequence exactly.

    A newline either replaces a separator the program already had or is
    inserted between two adjacent commands, so splitting on whitespace
    recovers the original token sequence.  No command is dropped,
    reordered, or split -- the corruption a character-count wrap causes in
    the multi-character-token languages.
    """
    example = _example(name)
    plain = example.build(width=None)
    wrapped = example.build(width)
    if wrapped == plain:
        # A program short enough to need no break is left alone; there is
        # nothing to undo.
        return
    # The grid pads each token into a right-aligned cell, so the original is
    # not recoverable character for character -- the padding is new
    # whitespace.  What must survive is the token sequence, which is the
    # guarantee the character-for-character check stands in for everywhere
    # else: no command dropped, reordered, or split.  The interpreters split
    # on whitespace runs, so a program with the same token sequence is the
    # same program.
    if _is_grid(name):
        assert wrapped.split() == plain.split()
        return
    # BIO indents by nesting depth, and its commands carry no separator at
    # all -- the whole program is one whitespace-delimited token, so the
    # token check above says nothing about it.  What must survive is the
    # command text; BIO's own parse rejoins across whitespace before reading
    # it, so a program the wrapper breaks where a space already stood is the
    # same program even though the space is gone.  Comparing with all
    # whitespace removed says exactly that, where stripping only the indent
    # asserted the spacing too and failed at a width that happened to break
    # on one.
    if WRAPPERS[LANGUAGES[name].id] is _bio:
        assert "".join(wrapped.split()) == "".join(plain.split())
        return
    # Taglate's first line is a structural queue seed the wrapper must leave
    # alone; only the commands below it are reflowed.
    if LANGUAGES[name].id in MULTILINE:
        seed, _, rest = wrapped.partition("\n")
        plain_seed, _, plain_rest = plain.partition("\n")
        assert seed == plain_seed
        assert rest.replace("\n", "") == plain_rest.replace("\n", "")
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
    wrapped = _example(name).build(DEFAULT_WIDTH)
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
    which would make the round-trip tests above pass vacuously.  Each
    assertion carries the language, since a wrapper that stopped firing
    fails here as a named language rather than as a thinner sweep.

    The language's own example is tried first, since it is the program the
    wrapper actually ships against.  Some are too terse to need a break at
    all (Sophie's is 37 characters, %^2^-1's is 5), so the table then grows
    until the program is long enough -- the way the text once did.  A
    parameterized generator leaves a ``{X0}`` placeholder that its example's
    ``fill`` replaces and the wrapper refuses, which is why the example
    comes first rather than the grown table.
    """
    example = _example(name)
    raw = example.build(width=None)
    if example.build(40) != raw:
        return
    structural = LANGUAGES[name].id in MULTILINE
    for arity in range(1, 5):
        grown = generate(name, _table(arity))
        # A newline disqualifies a grown program only where it means layout.
        # A :data:`MULTILINE` language starts with a structural row its
        # wrapper keeps and folds the rest, so the question there is whether
        # wrapping adds *more* rows, not whether any exist -- and whether the
        # part it may fold is itself long enough to need a break.  Measuring
        # the whole program instead stops the search at the first arity whose
        # *header* pushes it past the width, which for %^2^-1 is an arity
        # whose body is still thirteen characters.
        foldable = grown.split("\n", 1)[1] if structural else grown
        if ("\n" in grown and not structural) or len(foldable) <= 40:
            continue
        narrowed = generate(name, _table(arity), 40)
        assert narrowed.count("\n") > grown.count("\n"), f"{name}: wrapper never fired"
        return
    pytest.fail(f"{name}: no table up to 4 inputs produced a program long enough")


@pytest.mark.parametrize("name", sorted(UNWRAPPABLE))
def test_unwrappable_languages_are_untouched(name: str) -> None:
    """A language that cannot take newlines ignores the width."""
    language = next(lang for lang in LANGUAGES.values() if lang.id == name)
    assert language.id not in WRAPPERS, UNWRAPPABLE[name]
    program = "iiiioddo"
    assert wrap_program(program, language.id, 4) == program


@pytest.mark.parametrize("name", WIDTH_HONOURING)
def test_width_honouring_languages_respect_the_width(name: str) -> None:
    """A generator that lays itself out really does fit the width given.

    ``wrap_program`` cannot help these -- their newlines are layout -- so
    the width has to be honoured by the generator itself.

    Only the bound is asserted, not that a generous width reproduces the
    unbounded form byte for byte.  These generators lay the program out
    whenever they are given a width at all, so LaserFuck at a width its
    compact form already fits still folds its beam differently; that is the
    generator's layout choice rather than a wrap, and pinning it here would
    pin the layout, not the width.
    """
    language = next(lang for lang in LANGUAGES.values() if lang.id == name)
    assert language.id not in WRAPPERS, f"{name} both lays out and reflows"
    assert language.boolean is not None
    for width in (40, 80, 94):
        program = generate(language.name, TABLE, width)
        assert max(map(len, program.split("\n"))) <= width
    # omitting the width is still the compact one-shot form
    assert generate(language.name, TABLE) == language.boolean(TABLE)


@pytest.mark.parametrize("name", WRAPPED)
def test_no_width_is_unchanged(name: str) -> None:
    """Omitting the width reproduces exactly what the generator always gave.

    This is what keeps the committed examples byte-identical: the sync
    tests in ``tests/scripts/test_examples.py`` call the generators with no width.
    """
    lang = LANGUAGES[name]
    assert lang.boolean is not None
    assert generate(name, TABLE) == lang.boolean(TABLE)


def test_between_is_no_longer_wrapped_and_still_computes_its_table() -> None:
    """Between's wrapper went with the text generators that fed it.

    Its own programs are one instruction per line and none reaches a
    readable width, so the bespoke statement-splitting wrapper had no
    producer left; the width is now a no-op for it, and the program must
    still compute its table.
    """
    from esolangs.tools import boolean

    assert "between" not in WRAPPERS
    for table, bits in (("01", 1), ("0110", 2), ("01101001", 3)):
        program = boolean.between(table)
        for width in (5, 20, 40):
            assert wrap_program(program, "between", width) == program
        for row, expected in enumerate(table):
            stdin = "".join(b + "\n" for b in format(row, f"0{bits}b"))
            assert run("Between", program, stdin) == expected


def test_clockwise_is_never_reflowed() -> None:
    """Clockwise honours a width by shaping, never by inserting newlines.

    Its grid rows are semantic, so ``wrap_program`` must leave it alone even
    though ``generate`` does respond to a width for it -- the width reaches
    the generator instead.
    """
    assert "clockwise" not in WRAPPERS
    grid = generate("Clockwise", TABLE)
    assert wrap_program(grid, "clockwise", 10) == grid


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
    program = generate("Polynomial", TABLE, DEFAULT_WIDTH)
    assert "\n" in program
    assert not [line for line in program.split("\n") if line.strip() in ("+", "-")]


def test_polynomial_puts_one_term_on_each_line() -> None:
    """The layout: every line is exactly one term, sign included.

    A packed line would hold however many terms happened to fit, so its
    breaks would fall where the arithmetic landed rather than between two
    things a reader wants separated.
    """
    program = generate("Polynomial", TABLE, DEFAULT_WIDTH)
    lines = program.split("\n")
    # Line 1 is ``f(x) = <term>``; every other line is ``<sign> <term>``.
    assert lines[0].startswith("f(x) = ")
    # ``f(x)``, ``=`` and the unsigned leading term.
    assert len(lines[0].split()) == 3
    assert all(len(line.split()) == 2 for line in lines[1:])


def test_polynomial_continuation_lines_start_with_their_sign() -> None:
    """Every line but the first opens with the sign of its term."""
    program = generate("Polynomial", TABLE, DEFAULT_WIDTH)
    lines = program.split("\n")
    assert all(line.startswith(("+ ", "- ")) for line in lines[1:])


def test_polynomial_wrap_is_undone_by_swapping_newlines_for_spaces() -> None:
    """The wrap only moves separators, so the program is byte-identical."""
    plain = generate("Polynomial", TABLE)
    wrapped = generate("Polynomial", TABLE, DEFAULT_WIDTH)
    assert wrapped.replace("\n", " ") == plain


def test_polynomial_keeps_the_header_with_the_first_term() -> None:
    """``f(x)`` and ``=`` are not terms and do not get lines of their own."""
    assert _polynomial("f(x) = x^2 - 3x + 7", 80).split("\n")[0] == "f(x) = x^2"


def test_polynomial_layout_does_not_depend_on_the_width() -> None:
    """One term to a line whatever the width -- it is only the on/off switch.

    The terms of any interesting program outrun any width, so packing them
    to one would be a layout that changed with a number nobody chose.
    """
    program = generate("Polynomial", TABLE)
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


# A three-level nest around a short ramp, in the shape the boolean BIO
# generator emits: each level decrements ``x`` and the innermost tops ``y``
# up before the closers unwind.
_NESTED_BIO = "0ox; 0ix{1ox;0ix{1ox;0oy;};};0oy;0oy;1iy;"


def _bio_tokens(program: str) -> list[str]:
    """The commands BIO's own parser keeps, in order.

    The interpreter's regex drops everything else -- whitespace and the
    decorative ``{`` alike -- so two programs with this same list are the
    same program.
    """
    return re.findall(r"[01][oOiI][xXyYzZ](?:\{|;)|\};", program)


def test_bio_indents_a_nested_program_by_depth() -> None:
    """Each loop level is two spaces deeper than the one outside it."""
    lines = _bio(_NESTED_BIO, DEFAULT_WIDTH).split("\n")
    indents = [len(line) - len(line.lstrip(" ")) for line in lines]
    assert indents == [0, 2, 4, 2, 0, 0]


def test_bio_keeps_a_brace_with_the_command_that_opens_it() -> None:
    """``{`` marks the body of the ``0i?`` before it and never leads a line."""
    lines = _bio(_NESTED_BIO, DEFAULT_WIDTH).split("\n")
    assert not any(line.lstrip(" ").startswith("{") for line in lines)
    assert [line for line in lines if line.rstrip().endswith("{")]


def test_bio_indent_preserves_the_command_sequence() -> None:
    """Indenting is whitespace only: the parser sees the same commands."""
    wrapped = _bio(_NESTED_BIO, DEFAULT_WIDTH)
    assert _bio_tokens(wrapped) == _bio_tokens(_NESTED_BIO)


def test_bio_leaves_a_flat_program_packed() -> None:
    """A program under two levels deep gains no indentation.

    A flat run of depth-1 groups, where indenting would show nothing that
    packing does not.
    """
    flat = "0ox;0ix{1ox;0oy;};0oy;1iy;"
    wrapped = _bio(flat, DEFAULT_WIDTH)
    assert not any(line.startswith(" ") for line in wrapped.split("\n"))


def test_bio_packs_a_ramp_to_the_width_at_its_own_indent() -> None:
    """A long straight run costs rows at its level, not one long line."""
    program = "0ox;0ix{" + "0oy;" * 40 + "0ix{1ox;};};"
    lines = _bio(program, 20).split("\n")
    assert max(len(line) for line in lines) <= 20
    # The ramp sits inside the outer loop, so every one of its rows is
    # indented rather than only the first.
    ramp = [line for line in lines if "0oy" in line]
    assert len(ramp) > 1
    assert all(line.startswith("  ") for line in ramp)


def test_bio_indent_stops_growing_before_it_crowds_the_line() -> None:
    """A deep program keeps room to pack, and still unwinds its closers."""
    depth = 40
    program = "0ox;" + "0ix{" * depth + "1ox;" + "};" * depth
    lines = _bio(program, 20).split("\n")
    assert max(len(line) for line in lines) <= 20
    assert _bio_tokens("\n".join(lines)) == _bio_tokens(program)


def test_bio_indent_leaves_no_trailing_whitespace() -> None:
    """No line carries the separator the boolean generator writes."""
    wrapped = _bio(_NESTED_BIO, DEFAULT_WIDTH)
    assert all(line == line.rstrip() for line in wrapped.split("\n"))


def test_wrappers_refuse_input_they_do_not_recognize() -> None:
    """Each wrapper hands back anything outside the shape it knows.

    A wrapper only ever sees its own generator's output in practice, so
    these guards never fire there -- but they are what keeps a wrapper from
    half-transforming a program it does not understand, and a half-wrapped
    program is the failure mode the whole module exists to prevent.
    """
    # An empty program has no tokens to pack, in either packer.
    assert wrap_space_delimited("", 40) == ""
    assert wrap_grid("", 40) == ""
    # BIO's tokens have to tile the program exactly; a stray character means
    # the regex did not account for something, so the program is left alone.
    assert _bio("0ox;!!!", 40) == "0ox;!!!"
    # Taglate needs a queue seed *and* commands below it.
    assert _taglate("seed-only", 40) == "seed-only"


def test_polynomial_leaves_a_program_too_short_to_have_a_header() -> None:
    """The ``f(x) =`` header is three terms; a shorter program has none.

    Joining the first three terms only makes sense once they are the header,
    so a program that does not start that way is returned as it came.
    """
    assert _polynomial("1", 10) == "1"


def test_six_five_keeps_an_operand_with_its_command() -> None:
    """``7``/``8`` take the next character, so a break never lands between.

    The interpreter merges the pair without inspecting it, so a newline in
    the gap becomes the operand -- and ``num("\\n")`` is -45, a value no cell
    can hold.
    """
    program = "657812A"
    for width in range(2, 10):
        for line in _six_five(program, width).split("\n"):
            assert not line.endswith(("7", "8")), f"width {width} split an operand"


def test_six_five_keeps_a_guard_with_the_instruction_it_skips() -> None:
    """``7n`` skips the next *token*, and a newline is one.

    ``706A`` prints nothing and leaves cell 0 -- the ``70`` skips the ``6``.
    Break between them and the skip eats the newline instead, so the ``6``
    runs: the guard is defeated and the cell ends at 6.  The wrapper must
    therefore bind a ``7n`` to whatever follows it.
    """
    program = "70621A"
    unwrapped = _run("6-5", program)
    for width in range(2, 12):
        assert _run("6-5", _six_five(program, width)) == unwrapped


def test_six_five_wrapped_programs_still_run() -> None:
    """A wrapped 6-5 program computes what the unwrapped one computed."""
    program = generate("6-5", TABLE)
    unwrapped = _run("6-5", program)
    for width in (3, 5, 8, 13, 40, 60):
        assert _run("6-5", _six_five(program, width)) == unwrapped
