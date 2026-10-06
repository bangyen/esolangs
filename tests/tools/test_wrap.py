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
    DEFAULT_WIDTH,
    MULTILINE,
    WRAPPERS,
    _bio,
    _bitdeque,
    _cell_width,
    _mammalian,
    _packlang,
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
from tests.divergence import diverges, terminates

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

# Languages that must never be *reflowed*, and why.  Not a restatement of
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
UNWRAPPABLE = {
    "slashes": "newlines are literal output and substitution data",
    "fargo": "each physical line is one command; expressions have no continuation",
    "minsky_swap": "only line 1 is code; line 2 gives its numeric jump distances",
    "alight": "a command is a word walked cell by cell; a row end cuts it",
    "super_snusp": "a row is a grid row; a break moves code, it does not reflow",
    "algebraic_programming_language": "a line with '=' defines, one without runs",
    "arrowqueue": "the queue and decision tree occupy fixed grid coordinates",
    "back": "the beam path and embedded input occupy fixed grid coordinates",
    "befunge": "a row is a grid row and the lookup table is indexed by column",
    "fish": "a row is a codebox row and the lookup table is indexed by column",
    "underload": "a break inside a pushed element changes the string it contains",
    "brainif": "each line is one instruction and goto targets are line numbers",
    "clockwise": "a row is a ring row; the walk's turns sit at fixed cells",
    "collatz_multiverse": "each line is one complete register assignment",
    "container": "each line declares a container or one of its rules",
    "crement": "each line is one instruction; jumps and patches name line numbers",
    "inject": "blocks and executable commands are delimited by source lines",
    "thue": "a newline ends a rule, and the state's own newlines are part of it",
    "thisthat": "the H-tree's nodes and wires occupy fixed grid coordinates",
}

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
WIDTH_EXCEPTIONS = {
    "slashes": "newlines are literal output and substitution data",
    "line": "tree geometry fixes the width; balance chooses orientation",
}

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


def test_every_generator_has_a_width_policy() -> None:
    """Every generator reflows, lays itself out, or records why it cannot."""
    boolean_ids = {
        language.id for language in LANGUAGES.values() if language.boolean is not None
    }
    missing = {
        language.id
        for language in LANGUAGES.values()
        if language.boolean is not None
        and language.id not in WRAPPERS
        and not takes_width(language.boolean)
        and language.id not in WIDTH_EXCEPTIONS
    }
    assert missing == set()
    assert set(WIDTH_EXCEPTIONS) <= boolean_ids
    assert all(reason.strip() for reason in WIDTH_EXCEPTIONS.values())
    assert set(UNWRAPPABLE) <= boolean_ids
    assert all(reason.strip() for reason in UNWRAPPABLE.values())


def _table(arity: int) -> str:
    """The parity (XOR) table on ``arity`` inputs."""
    return "".join(str(bin(row).count("1") & 1) for row in range(2**arity))


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
        return run(name, program, _stdin(name))
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


@pytest.mark.parametrize("name", WRAPPED)
def test_wrapping_only_breaks_between_tokens(name: str) -> None:
    """Wrapping preserves the token sequence exactly."""
    width = NARROW_WIDTH
    example = _example(name)
    if takes_width(example.generator):
        plain = example.build(width)
        wrapped = wrap_program(plain, LANGUAGES[name].id, max(1, width // 2))
        if name == "Packlang":
            from esolangs.interpreters.other.packlang import _tokenize

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
        grown = _grown(name, _table(arity), None)
        # A newline disqualifies a grown program only where it means layout.
        # A :data:`MULTILINE` language starts with a structural row its
        # wrapper keeps and folds the rest, so the question there is whether
        # wrapping adds *more* rows, not whether any exist -- and whether the
        # part it may fold is itself long enough to need a break.
        foldable = grown.split("\n", 1)[1] if structural and "\n" in grown else grown
        if ("\n" in grown and not structural) or len(foldable) <= 40:
            continue
        narrowed = _grown(name, _table(arity), 40)
        assert narrowed.count("\n") > grown.count("\n"), f"{name}: wrapper never fired"
        return
    pytest.fail(f"{name}: no table up to 4 inputs produced a program long enough")


def _grown(name: str, table: str, width: int | None) -> str:
    """A runnable program for ``table``: the template filled with zeros."""
    if _example(name).fill is None:
        return generate(name, table, width)
    arity = len(table).bit_length() - 1
    return esolangs.instantiate(name, generate(name, table), [0] * arity, width)


# Tables the generators take a *different path* on than parity.  The
# committed examples are all AND2, and the sweeps above grow parity, so
# between them they exercise two shapes -- and a wrapper is exercised by the
# shape of the program, not by the table directly.  Sophie's else-block bug
# needed a table that puts an if-block beside an else-block, which neither
# AND2 nor parity produces at three inputs; majority does.
_OTHER_TABLES = {"majority": "00010111", "mixed": "11111001"}

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
        return run(name, program, stdin, timeout=_RUN_TIMEOUT)
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
        tables = {**tables, "parity5": _table(5)}
    if name == "thue":
        tables = {**tables, "parity4": _table(4)}
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
        tables = {**tables, "parity5": _table(5)}
    if name == "thue":
        tables = {**tables, "parity4": _table(4)}
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


@pytest.mark.parametrize("name", sorted(UNWRAPPABLE))
def test_unwrappable_languages_are_untouched(name: str) -> None:
    """A language that cannot take newlines ignores the width."""
    language = next(lang for lang in LANGUAGES.values() if lang.id == name)
    assert language.id not in WRAPPERS, UNWRAPPABLE[name]
    program = "iiiioddo"
    assert wrap_program(program, language.id, 4) == program


def test_clockwise_is_never_reflowed() -> None:
    """Clockwise takes no width, and a break in its grid is not a reflow."""
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


@pytest.mark.parametrize(
    ("program", "token"),
    [
        ("+=30.", "=30"),
        ("+:x.", ":x"),
        ("+>~3.", ">~3"),
        ("+!12.", "!12"),
        ("+?7.", "?7"),
        ("+$4.", "$4"),
        ("+{2}.", "{2"),
    ],
)
def test_dimensional_keeps_every_operand_with_its_command(
    program: str, token: str
) -> None:
    """A break inside any of these changes what the program does."""
    assert token in wrap_program(program, "dimensional", 1).split("\n")


def test_wrap_tokens_refuses_a_pattern_that_does_not_tile() -> None:
    """A pattern that drops characters returns the program unwrapped."""
    assert wrap_tokens("aXbXc", 2, "[abc]") == "aXbXc"


def test_wrap_space_delimited_never_splits_a_token() -> None:
    """A token longer than the width gets its own line, unbroken."""
    wrapped = wrap_space_delimited("1 22 333333 4", 3)
    assert "333333" in wrapped.split("\n")
    assert wrapped.replace("\n", " ") == "1 22 333333 4"


def test_polynomial_never_strands_a_sign_on_its_own_line() -> None:
    """The raggedness this wrapper exists to fix: a line that is just a sign."""
    program = generate("Polynomial", TABLE, DEFAULT_WIDTH)
    assert "\n" in program
    assert not [line for line in program.split("\n") if line.strip() in ("+", "-")]


def test_polynomial_starts_a_term_only_on_a_line_of_its_own() -> None:
    """The layout: a term starts a line, and only ever at the start of one."""
    program = generate("Polynomial", TABLE, DEFAULT_WIDTH)
    lines = program.split("\n")
    # Line 1 is ``f(x) = <term>``: ``f(x)``, ``=`` and the unsigned term.
    assert lines[0].startswith("f(x) = ")
    assert len(lines[0].split()) == 3
    for line in lines[1:]:
        # Either a line that starts a term -- ``<sign> <term>`` -- or a row
        # carrying the previous one over, which is one unbroken run.
        assert len(line.split()) == (2 if line.startswith(("+ ", "- ")) else 1)


def test_polynomial_carries_a_term_over_without_inventing_a_sign() -> None:
    """A row continuing a term is bare: the sign belongs to the term's start."""
    # Four-input parity: XOR's coefficients no longer reach the width now
    # that the generator spells itself on the cheap opcodes.
    program = generate("Polynomial", "0110100110010110", DEFAULT_WIDTH)
    carried = [
        line for line in program.split("\n")[1:] if not line.startswith(("+ ", "- "))
    ]
    assert carried, "the table is too small to fold a term -- pick a wider one"
    assert all(line.strip() and " " not in line for line in carried)


def test_polynomial_wrap_is_undone_by_deleting_whitespace() -> None:
    """The wrap only inserts newlines, so the parsed program is unchanged."""
    plain = generate("Polynomial", TABLE)
    wrapped = generate("Polynomial", TABLE, DEFAULT_WIDTH)
    assert wrapped != plain
    assert re.sub(r"\s", "", wrapped) == re.sub(r"\s", "", plain)


def test_polynomial_keeps_the_header_with_the_first_term() -> None:
    """``f(x)`` and ``=`` are not terms and do not get lines of their own."""
    assert _polynomial("f(x) = x^2 - 3x + 7", 80).split("\n")[0] == "f(x) = x^2"


def test_polynomial_meets_the_width_it_is_given() -> None:
    """Every row fits, at every width -- the coefficients fold too."""
    program = generate("Polynomial", TABLE)
    for width in (13, 40, 80, 200):
        for line in _polynomial(program, width).split("\n"):
            assert len(line) <= width


def test_polynomial_keeps_an_oversized_term_with_its_sign() -> None:
    """A term wider than the width keeps its sign rather than shedding it."""
    wrapped = _polynomial("f(x) = x^2 - 123456789x + 7", 12)
    assert "- 123456789x" in wrapped.split("\n")


def test_polynomial_leaves_a_trailing_sign_alone() -> None:
    """A sign with no term after it is kept rather than dropped."""
    assert _polynomial("f(x) = x +", 80) == "f(x) = x\n+"


def test_polynomial_keeps_a_sign_with_no_term_to_attach_to() -> None:
    """Two signs in a row: the first has no term, and is kept as a line."""
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


def test_mammalian_uses_seed_sized_cells() -> None:
    """Every command starts on the SEED-sized lattice."""
    wrapped = _mammalian(
        "SEED SEED DIGEST ACCEPT LEAPFROG PRONOUNCE CONFLAGRATE SEED", 39
    )
    assert wrapped.split("\n") == [
        "SEED SEED DIGEST    ACCEPT    LEAPFROG",
        "PRONOUNCE CONFLAGRATE    SEED",
    ]
    for row in wrapped.split("\n"):
        assert all(match.start() % 5 == 0 for match in re.finditer(r"\S+", row))


def test_wrap_chars_breaks_anywhere() -> None:
    """The single-character families break at exactly the width."""
    assert wrap_chars("abcdef", 2) == "ab\ncd\nef"


# A three-level nest around a short ramp, in the shape the boolean BIO
# generator emits: each level decrements ``x`` and the innermost tops ``y``
# up before the closers unwind.
_NESTED_BIO = "0ox; 0ix{1ox;0ix{1ox;0oy;};};0oy;0oy;1iy;"


def _bio_tokens(program: str) -> list[str]:
    """The commands BIO's own parser keeps, in order."""
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
    """A program under two levels deep gains no indentation."""
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
    """Each wrapper hands back anything outside the shape it knows."""
    # An empty program has no tokens to pack, in either packer.
    assert wrap_space_delimited("", 40) == ""
    assert wrap_grid("", 40) == ""
    # BIO's tokens have to tile the program exactly; a stray character means
    # the regex did not account for something, so the program is left alone.
    assert _bio("0ox;!!!", 40) == "0ox;!!!"
    # Unknown punctuation must survive Packlang lexical folding verbatim.
    unknown = "package t { invalid@token; }"
    assert _packlang(unknown, 1) == unknown
    # Taglate needs a queue seed *and* commands below it.
    assert _taglate("seed-only", 40) == "seed-only"


def test_polynomial_leaves_a_program_too_short_to_have_a_header() -> None:
    """The ``f(x) =`` header is three terms; a shorter program has none."""
    assert _polynomial("1", 10) == "1"


def test_six_five_keeps_an_operand_with_its_command() -> None:
    """``7``/``8`` take the next character, so a break never lands between."""
    program = "657812A"
    for width in range(2, 10):
        for line in _six_five(program, width).split("\n"):
            assert not line.endswith(("7", "8")), f"width {width} split an operand"


def test_six_five_keeps_a_guard_with_the_instruction_it_skips() -> None:
    """``7n`` skips the next *token*, and a newline is one."""
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


def test_mammalian_hands_back_a_program_with_no_words() -> None:
    """The grid wrapper needs at least one token to size a row, so a
    whitespace-only program is returned as it came."""
    assert _mammalian("", 40) == ""
    assert _mammalian("   \n ", 40) == "   \n "
