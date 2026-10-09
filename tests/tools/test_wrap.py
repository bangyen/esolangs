"""Wrapping a generated program must not change what it does."""

import re
from dataclasses import replace
from functools import cache

import pytest

import esolangs
from esolangs import generate, run
from esolangs.registry import LANGUAGES, canonical_id
from esolangs.tools.examples import BOOLEAN_EXAMPLES as BOOLEAN_GENERATED
from esolangs.tools.examples import BooleanExample
from esolangs.tools.wrap import (
    MULTILINE,
    WRAPPERS,
    _bio,
    _bitdeque,
    _cell_width,
    _mammalian,
    _packlang,
    _polynomial,
    _span,
    takes_width,
    wrap_chars,
    wrap_grid,
    wrap_program,
    wrap_space_delimited,
    wrap_tokens,
)
from tests.divergence import diverges, terminates
from tests.generator_support import CHECK
from tests.witness_tables import parity

# A 2-input table (XOR), which every boolean generator can build.  Used
# where a test needs *a* program rather than the language's own example.
TABLE = "0110"


def _public(lang: object, table: str) -> str:
    """What ``generate`` returns with no width: the generator's own output,
    rendered to the public run form for a parameterized language."""
    from esolangs.registry import parameterized_ids, render_template

    assert lang.boolean is not None  # type: ignore[attr-defined]
    text = lang.boolean(table)  # type: ignore[attr-defined]
    if lang.id in parameterized_ids():  # type: ignore[attr-defined]
        n = len(table).bit_length() - 1
        return render_template(lang.id, text, n)[0]  # type: ignore[attr-defined]
    return text


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

# Languages that must never be *reflowed*, and why: each ``LANGUAGE``'s
# ``no_wrap=``.  Not a restatement of
# the implementation: each was verified to break (or to be meaningless) when
# newlines are inserted, so the table is the record of that finding.
#
# Four of them are already covered by a general rule and named anyway,
# because each has a *specific* reason worth keeping rather than deriving
# again.  Alight and Super SNUSP are 2D, where a newline is a row: Alight's
# commands are words walked out cell by cell, so a row end cuts one in
# half, and Super SNUSP's pointer walks a grid, so a break relocates code
# rather than reflowing it.  (The older reason given here -- that with no
# start marker it enters at the bottom right -- is true of the language but
# not of these programs, which all begin with an explicit ``"``.)  Both now
# take a width themselves, by folding on their own turns and mirrors; that
# is the independence the paragraph below is about.  function x(y) and the
# Algebraic Programming Language are line-structured source rather than
# grids -- the first takes one indented statement per line, the second
# decides a line's *meaning* by whether it contains an ``=``, so a break
# does not reflow a line but turns one line into two with different jobs.
#
# Unwrappable is not the same as unbounded, and the two memberships are
# independent: a language here may still take a width by *emitting* a
# narrower program, which is what function x(y) does by naming its
# subtrees.  What this table says is only that :func:`wrap_program` must
# not touch the finished text -- the reasons above are why a break is
# destructive, and those hold whatever the generator learns to do.
UNWRAPPABLE = {lang.id: lang.no_wrap for lang in LANGUAGES.values() if lang.no_wrap}

# These are 2D too, and wrap_program must not touch them either -- but each
# honours a width itself by *laying its program out* to fit rather than by
# ignoring it, so they belong here rather than in UNWRAPPABLE.  LaserFuck's
# loop layout is tied to the beam's track and cannot fold, so a loop program
# wider than the width is re-emitted as the (foldable) linear form.
#
# Derived from :func:`takes_width` rather than written out, for the reason
# ``esolangs.tools.BOOLEAN`` is derived from the registry: the
# hand-written table had drifted both ways.  It omitted Streetcode, which
# really does take a width.  And it named Dig, which at the time took only
# a truth table and returned the same program whatever width was asked for
# -- the 2-input table below was inside 80 columns either way, which is
# what let it pass.  Dig has since grown a real one, so that entry would be
# right today for a reason the table never had; a derived table cannot make
# either mistake in the first place.
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


def _wrapper_witnesses() -> list[str]:
    """Every width-taking language, plus one per (wrapper, template) otherwise.

    Without a width the check is textual, so 14 plain wrap_chars languages
    ran one assertion on one code path; a template takes wrap_chars' mark
    branch, so it is its own class.
    """
    seen: set[tuple[object, bool]] = set()
    chosen = []
    for name in WRAPPED:
        example = EXAMPLE_BY_ID[LANGUAGES[name].id]
        key = (WRAPPERS[LANGUAGES[name].id], example.fill is None)
        if takes_width(example.generator) or key not in seen:
            seen.add(key)
            chosen.append(name)
    return chosen


def test_every_generator_has_a_width_policy() -> None:
    """Every generator reflows, lays itself out, or records why it cannot."""
    missing = {
        language.id
        for language in LANGUAGES.values()
        if language.boolean is not None
        and language.id not in WRAPPERS
        and not takes_width(language.boolean)
        and not language.no_wrap.strip()
    }
    assert not missing, f"{sorted(missing)} have no width policy; {CHECK}"


def _example(name: str) -> BooleanExample:
    """The boolean example for ``name``, which the sweep is driven by."""
    return EXAMPLE_BY_ID[LANGUAGES[name].id]


def _stdin(name: str) -> str:
    """Return the example's encoded stdin."""
    return _example(name).stdin


def _replaces_a_space(name: str) -> bool:
    """Whether ``name``'s wrapper breaks at a space rather than between commands."""
    return WRAPPERS[LANGUAGES[name].id] in (
        wrap_space_delimited,
        _polynomial,
        _bitdeque,
    )


def _is_grid(name: str) -> bool:
    """Whether ``name``'s wrapper lays its tokens out as a padded grid."""
    return WRAPPERS[LANGUAGES[name].id] in (wrap_grid, _mammalian)


def _run(name: str, program: str) -> str:
    """What ``program`` does under ``name``'s interpreter: output, or a raise."""
    try:
        return run(name, program, stdin=_stdin(name))
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


@pytest.mark.parametrize("name", _wrapper_witnesses())
def test_wrapping_only_breaks_between_tokens(name: str) -> None:
    """Wrapping preserves the token sequence exactly."""
    width = NARROW_WIDTH
    example = _example(name)
    if takes_width(example.generator):
        plain = example.build(width)
        wrapped = wrap_program(plain, LANGUAGES[name].id, max(1, width // 2))
        if name == "Packlang":
            from esolangs.interpreters.other._packlang_lex import _tokenize

            assert _tokenize(wrapped) == _tokenize(plain)
        elif name in {"FRACTRAN", "RAM0"}:
            assert wrapped.split() == plain.split()
        else:
            assert wrapped.replace("\n", "") == plain.replace("\n", "")
        assert _run(name, wrapped) == _run(name, plain)
        return
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
    # These are multi-line with no structural first line. Their parsers see
    # whitespace-delimited tokens across the whole source, so flattening and
    # repacking may move every original line break.
    if LANGUAGES[name].id in {"qoibl", "forbin"}:
        assert wrapped.split() == plain.split()
        return
    # Taglate's first line is a structural queue seed the wrapper must leave
    # alone; only the commands below it are reflowed.
    if LANGUAGES[name].id in MULTILINE and "\n" in plain:
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
    # Polynomial now breaks in both places -- between two terms, where a
    # space was, and *inside* a coefficient, where nothing was -- so no
    # single substitution restores it.  Its parser deletes whitespace
    # before reading, so the invariant that means anything there is that
    # the two agree once whitespace is gone.
    if WRAPPERS[LANGUAGES[name].id] is _polynomial:
        assert re.sub(r"\s", "", wrapped) == re.sub(r"\s", "", plain)
        return
    restored = wrapped.replace("\n", " ") if _replaces_a_space(name) else wrapped
    assert restored.replace("\n", "") == plain


@pytest.mark.parametrize("name", WRAPPED)
def test_every_wrapper_actually_fires(name: str) -> None:
    """Every language in the table really does wrap, given enough program."""
    example = _example(name)
    raw = example.build(width=None)
    if example.build(40) != raw:
        return
    # Packlang already emits one short, indented statement per line.  Its
    # wrapper exists for a caller's wider hand-written line; the focused
    # ``_packlang`` tests supplies that positive control.
    if WRAPPERS[LANGUAGES[name].id] is _packlang and all(
        len(line) <= 40 for line in raw.splitlines()
    ):
        return
    structural = LANGUAGES[name].id in MULTILINE
    for arity in range(1, 5):
        grown = _grown(name, parity(arity), None)
        # A newline disqualifies a grown program only where it means layout.
        # A :data:`MULTILINE` language starts with a structural row its
        # wrapper keeps and folds the rest, so the question there is whether
        # wrapping adds *more* rows, not whether any exist -- and whether the
        # part it may fold is itself long enough to need a break.
        foldable = grown.split("\n", 1)[1] if structural and "\n" in grown else grown
        if ("\n" in grown and not structural) or len(foldable) <= 40:
            continue
        narrowed = _grown(name, parity(arity), 40)
        assert narrowed.count("\n") > grown.count("\n"), f"{name}: wrapper never fired"
        return
    pytest.fail(f"{name}: no table up to 4 inputs produced a program long enough")


def _grown(name: str, table: str, width: int | None) -> str:
    """A runnable program for ``table``: the template filled with zeros."""
    if _example(name).fill is None:
        return generate(name, table, width=width)
    arity = len(table).bit_length() - 1
    return esolangs.instantiate(name, generate(name, table), [0] * arity, width=width)


# Long enough that a run which has not finished is looping, short enough
# that eight of them are not a wait.  123 answers by *looping forever* for a
# one, so a timeout is one of the behaviours being compared rather than a
# failure -- what must match is that the wrapped program loops exactly where
# the unwrapped one does.
#
# The bound is the whole cost of the 123 rows: `mixed` has six ones, run
# wrapped and unwrapped, so it was six times two times 5.0 -- 60s, to the
# hundredth.  The floor is the slowest halting run in this corpus, since one
# cut short would be misread as a loop; measured over every wrapped language
# and both tables below, that is 0.296s (Polynomial). Two seconds is 6.8x
# that here and about 2.7x with CI's slower cores.
_RUN_TIMEOUT = 2.0


@cache
def _behaviour(name: str, program: str, stdin: str) -> str:
    """What ``program`` does, as a value: its output, or how it failed."""
    if esolangs.describe(name)["answer_mode"] == "termination":
        return (
            "halts"
            if terminates(name, program, stdin, _RUN_TIMEOUT)
            else "diverges (cycle or timeout)"
        )
    if diverges(name, program, stdin):
        return "diverges (cycle proven)"
    try:
        return run(name, program, stdin=stdin, timeout=_RUN_TIMEOUT)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


# Tables and widths for the two generators that lay themselves out.  The
# widths reach well below what either can build, which is the point: the
# narrow end is where a layout generator has to decide what to do when the
# width cannot be met, and the test above this comment only ever asked for
# widths every program already fitted.
_HONOUR_TABLES = {
    "parity1": "01",
    "parity2": "0110",
    "parity3": "01101001",
    "majority3": "00010111",
}
_HONOUR_WIDTHS = (10, 20, 40, 80)


def _columns(program: esolangs.Program) -> int:
    """The width of the widest row of ``program``."""
    if isinstance(program, esolangs.Raster):
        return len(program.rows[0])
    return max(len(line) for line in program.split("\n"))


def _laid_out(name: str, table: str, bits: str, width: int | None) -> str:
    """``name``'s program for ``table`` and ``bits``, laid out to ``width``."""
    example = EXAMPLE_BY_ID[LANGUAGES[name].id]
    variant = replace(
        example,
        table=table,
        bits=tuple(int(bit) for bit in bits) if example.fill else (),
        inputs=() if example.fill else tuple(bits),
        scale=1,
    )
    return variant.build(width)


@pytest.mark.parametrize("name", WIDTH_HONOURING)
def test_width_honouring_layout_meets_any_width_it_can(name: str) -> None:
    """The layout fits the width whenever the generator can build it that narrow."""
    language = next(lang for lang in LANGUAGES.values() if lang.id == name)
    tables = _HONOUR_TABLES
    if name == "inject":
        tables = {**tables, "parity5": parity(5)}
    if name == "thue":
        tables = {**tables, "parity4": parity(4)}
    for label, table in tables.items():
        arity = len(table).bit_length() - 1
        bits = "0" * arity
        narrowest = _columns(_laid_out(language.name, table, bits, 1))
        for width in _HONOUR_WIDTHS:
            columns = _columns(_laid_out(language.name, table, bits, width))
            assert columns <= max(width, narrowest), (
                f"{name}: {label} at width {width} came out {columns} columns, "
                f"wider than both the width and its {narrowest}-column floor"
            )


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(name, marks=pytest.mark.slow)
        if name in {"streetcode", "vandevelo"}
        else name
        for name in WIDTH_HONOURING
    ],
)
# part of 6.7s: runs the wrapped program.
@pytest.mark.medium
def test_width_honouring_layout_computes_the_same_thing(name: str) -> None:
    """Laying the program out to a width does not change what it computes."""
    language = next(lang for lang in LANGUAGES.values() if lang.id == name)
    example = EXAMPLE_BY_ID[language.id]
    relaid = 0
    tables = _HONOUR_TABLES
    if name == "inject":
        tables = {**tables, "parity5": parity(5)}
    if name == "thue":
        tables = {**tables, "parity4": parity(4)}
    for label, table in tables.items():
        arity = len(table).bit_length() - 1
        for combo in range(2**arity):
            bits = format(combo, f"0{arity}b")
            # A parameterized generator embeds its inputs and reads nothing.
            stdin = (
                ""
                if example.fill
                else esolangs.encode_inputs(language.name, [int(bit) for bit in bits])
            )
            compact = _laid_out(language.name, table, bits, None)
            expected = _behaviour(language.name, compact, stdin)
            if name == "back":
                assert len(expected.split()) == arity + 1
                assert set(expected.split()) <= {"0", "1"}
                expected = esolangs.read_answer(language.name, expected)
                assert expected == table[combo]
            widths = (
                (1, *_HONOUR_WIDTHS)
                if name in {"arrowqueue", "container", "crement"}
                else _HONOUR_WIDTHS
            )
            for width in widths:
                folded = _laid_out(language.name, table, bits, width)
                relaid += folded != compact
                actual = _behaviour(language.name, folded, stdin)
                if name == "back":
                    # Its contract is cell n; earlier cells are scratch.
                    assert len(actual.split()) == arity + 1
                    assert set(actual.split()) <= {"0", "1"}
                    actual = esolangs.read_answer(language.name, actual)
                assert actual == expected, (
                    f"{name}: laying {label} out to width {width} changed the "
                    f"answer for inputs {bits}"
                )
    # A generator that stopped laying anything out would pass every
    # assertion above by comparing the compact form against itself.
    assert relaid, f"{name}: no width produced a different layout"


def test_unwrappable_languages_are_untouched() -> None:
    """No unwrappable language has a wrapper, so a one-line program is kept."""
    assert set(UNWRAPPABLE).isdisjoint(WRAPPERS)
    assert wrap_program("iiiioddo", "slashes", 4) == "iiiioddo"


def test_zero_and_negative_widths_do_not_wrap() -> None:
    """A nonsensical width is a no-op rather than an error or a crash."""
    for width in (0, -1):
        assert wrap_program("a b c", "decleq", width) == "a b c"


def test_already_multiline_programs_are_left_alone() -> None:
    """A program that already has newlines is never re-wrapped."""
    program = "line one\nline two"
    assert wrap_program(program, "decleq", 4) == program


def test_wrap_tokens_refuses_a_pattern_that_does_not_tile() -> None:
    """A pattern that drops characters returns the program unwrapped."""
    assert wrap_tokens("aXbXc", 2, "[abc]") == "aXbXc"


def test_wrap_space_delimited_never_splits_a_token() -> None:
    """A token longer than the width gets its own line, unbroken."""
    wrapped = wrap_space_delimited("1 22 333333 4", 3)
    assert "333333" in wrapped.split("\n")
    assert wrapped.replace("\n", " ") == "1 22 333333 4"


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
    assert wrapped.split("\n") == ["111 222 333", "444 555 666"]


def test_wrap_grid_leaves_no_trailing_whitespace() -> None:
    """Right-aligning pads on the left, so no line ends in a space."""
    wrapped = wrap_grid("1 22 333 4 5 66", 12)
    for line in wrapped.split("\n"):
        assert line == line.rstrip()


def test_wrap_grid_sizes_cells_to_the_bulk_not_the_outlier() -> None:
    """A lone wide token does not pad every other cell out to its width."""
    tokens = ["321"] * 20 + ["1000000000"]
    assert _cell_width(tokens) == 3
    # Without the outlier rule this would be 21 cells of width 10.
    wrapped = wrap_grid(" ".join(tokens), 80)
    assert wrapped.split("\n")[0] == " ".join(["321"] * 20)


def test_wrap_grid_spans_an_outlier_across_whole_cells() -> None:
    """A token too wide for one cell takes several, keeping the lattice."""
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


def test_wrappers_refuse_input_they_do_not_recognize() -> None:
    """Each wrapper hands back anything outside the shape it knows."""
    # An empty program has no tokens to pack, in either packer.
    assert wrap_space_delimited("", 40) == ""
    assert wrap_grid("", 40) == ""
