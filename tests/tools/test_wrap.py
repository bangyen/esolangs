r"""Wrapping a generated program must not change what it does."""

import re
from dataclasses import replace

import pytest

from esolangs import generate, run
from esolangs.registry import LANGUAGES, canonical_id
from esolangs.tools.boolean.examples import BOOLEAN_EXAMPLES as BOOLEAN_GENERATED
from esolangs.tools.boolean.examples import BooleanExample
from esolangs.tools.wrap import (
    _PCT_HEADER_END,
    DEFAULT_WIDTH,
    MULTILINE,
    WRAPPERS,
    _bio,
    _bitdeque,
    _cell_width,
    _polynomial,
    _qoibl,
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

# A 2-input table (XOR), which.
# where a test needs *a*.
TABLE = "0110"

# A third width, narrower than.
# wrapper is not broken at.
# multi-character token depends.
# wrapper can be wrong and.
# answered 1 instead of 0 at 12.
# correct, and the three.
# under wrap_chars at some.
# Sweeping a dozen widths per.
# width in the suite is what.
NARROW_WIDTH = 13

# Languages that must never be.
# the implementation: each was.
# newlines are inserted, so the.
# .
# The eight below NoComment.
# at every position of the.
# one.
# all; Alight has only the very.
# rather than splitting.
# could use: five sit inside.
# end of the program, so there.
# Either way there is no token.
# would help.
# is worth as much as a.
# otherwise looks like an.
# n == 4 and Super SNUSP 286.
# .
# Four of them are already.
# because each has a *specific*.
# again.
# commands are words walked out.
# half, and Super SNUSP's.
# rather than reflowing it.
# start marker it enters at the.
# not of these programs, which.
# take a width themselves, by.
# is the independence the.
# Algebraic Programming.
# grids -- the first takes one.
# decides a line's *meaning* by.
# does not reflow a line but.
# .
# Unwrappable is not the same.
# independent: a language here.
# narrower program, which is.
# subtrees.
# not touch the finished text.
# destructive, and those hold.
UNWRAPPABLE = {
    "nocomment": "a newline is an unrecognized command, a load error",
    "grapheme": "every character must be A-Z, so a newline is a load error",
    "cvnc": "the source must syllabify and a newline is in no syllable",
    "fargo": "its newlines already separate statements",
    "minsky_swap": "its second line is absolute offsets into its first",
    "alight": "a command is a word walked cell by cell; a row end cuts it",
    "super_snusp": "a row is a grid row; a break moves code, it does not reflow",
    "function_x_y": "its statements are one per line, and indented",
    "algebraic_programming_language": "a line with '=' defines, one without runs",
}

# These are 2D too, and.
# honours a width itself by.
# ignoring it, so they belong.
# loop layout is tied to the.
# wider than the width is.
# .
# Derived from.
# ``esolangs.tools.boolean.BOOLE.
# hand-written table had.
# really does take a width.
# a truth table and returned.
# -- the 2-input table below.
# what let it pass.
# right today for a reason the.
# either mistake in the first.
WIDTH_HONOURING = sorted(
    lang.id
    for lang in LANGUAGES.values()
    if lang.boolean is not None and takes_width(lang.boolean)
)

# The boolean example for each.
# than the example's stem.
# a lookup by id against a.
# skip, not a failure, so the.
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
    r"""The parity (XOR) table on ``arity`` inputs."""
    return "".join(str(bin(row).count("1") & 1) for row in range(2**arity))


def _example(name: str) -> BooleanExample:
    r"""The boolean example for ``name``, which the sweep is driven by."""
    return EXAMPLE_BY_ID[LANGUAGES[name].id]


def _stdin(name: str) -> str:
    r"""The input lines ``name``'s example feeds its program."""
    return "".join(f"{line}\n" for line in _example(name).inputs)


def _replaces_a_space(name: str) -> bool:
    r"""Whether ``name``'s wrapper breaks at a space rather than between."""
    return WRAPPERS[LANGUAGES[name].id] in (
        wrap_space_delimited,
        _polynomial,
        _bitdeque,
    )


def _is_grid(name: str) -> bool:
    r"""Whether ``name``'s wrapper lays its tokens out as a padded grid."""
    return WRAPPERS[LANGUAGES[name].id] is wrap_grid


def _run(name: str, program: str) -> str:
    r"""What ``program`` does under ``name``'s interpreter: output, or a."""
    try:
        return run(name, program, _stdin(name))
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


@pytest.mark.parametrize("name", WRAPPED)
@pytest.mark.parametrize("width", [NARROW_WIDTH, 40, DEFAULT_WIDTH])
def test_wrapped_program_prints_the_same(name: str, width: int) -> None:
    r"""A wrapped program behaves exactly as the unwrapped one behaves."""
    example = _example(name)
    assert _run(name, example.build(width)) == _run(name, example.build(width=None))


@pytest.mark.parametrize("name", WRAPPED)
@pytest.mark.parametrize("width", [NARROW_WIDTH, 40, DEFAULT_WIDTH])
def test_wrapping_only_breaks_between_tokens(name: str, width: int) -> None:
    r"""Wrapping preserves the token sequence exactly."""
    example = _example(name)
    plain = example.build(width=None)
    wrapped = example.build(width)
    if wrapped == plain:
        # A program short enough to.
        # nothing to undo.
        return
    # The grid pads each token into.
    # not recoverable character for.
    # whitespace.
    # guarantee the.
    # else: no command dropped,.
    # on whitespace runs, so a.
    # same program.
    if _is_grid(name):
        assert wrapped.split() == plain.split()
        return
    # BIO indents by nesting depth,.
    # all -- the whole program is.
    # token check above says.
    # command text; BIO's own parse.
    # it, so a program the wrapper.
    # same program even though the.
    # whitespace removed says.
    # asserted the spacing too and.
    # on one.
    if WRAPPERS[LANGUAGES[name].id] is _bio:
        assert "".join(wrapped.split()) == "".join(plain.split())
        return
    # Qoibl is multi-line with no.
    # statement and every one.
    # sequence across the whole.
    # Its newlines replace spaces,.
    if WRAPPERS[LANGUAGES[name].id] is _qoibl:
        assert wrapped.split() == plain.split()
        return
    # Taglate's first line is a.
    # alone; only the commands.
    if LANGUAGES[name].id in MULTILINE:
        seed, _, rest = wrapped.partition("\n")
        plain_seed, _, plain_rest = plain.partition("\n")
        assert seed == plain_seed
        assert rest.replace("\n", "") == plain_rest.replace("\n", "")
        return
    # Deleting the inserted.
    # The space-delimited wrappers.
    # there the newline turns back.
    # inserts the newline between.
    # away.
    # Polynomial now breaks in both.
    # space was, and *inside* a.
    # single substitution restores.
    # before reading, so the.
    # the two agree once whitespace.
    if WRAPPERS[LANGUAGES[name].id] is _polynomial:
        assert re.sub(r"\s", "", wrapped) == re.sub(r"\s", "", plain)
        return
    restored = wrapped.replace("\n", " ") if _replaces_a_space(name) else wrapped
    assert restored.replace("\n", "") == plain


@pytest.mark.parametrize("name", WRAPPED)
def test_wrapping_respects_the_width(name: str) -> None:
    r"""No line exceeds the width, unless a single token already does."""
    wrapped = _example(name).build(DEFAULT_WIDTH)
    for line in wrapped.split("\n"):
        longest_token = max((len(t) for t in line.split()), default=0)
        assert len(line) <= max(DEFAULT_WIDTH, longest_token)


@pytest.mark.parametrize("name", WRAPPED)
def test_every_wrapper_actually_fires(name: str) -> None:
    r"""Every language in the table really does wrap, given enough program."""
    example = _example(name)
    raw = example.build(width=None)
    if example.build(40) != raw:
        return
    structural = LANGUAGES[name].id in MULTILINE
    for arity in range(1, 5):
        grown = generate(name, _table(arity))
        # A newline disqualifies a.
        # A :data:`MULTILINE` language.
        # wrapper keeps and folds the.
        # wrapping adds *more* rows,.
        # part it may fold is itself.
        # the whole program instead.
        # *header* pushes it past the.
        # whose body is still thirteen.
        foldable = grown.split("\n", 1)[1] if structural else grown
        if ("\n" in grown and not structural) or len(foldable) <= 40:
            continue
        narrowed = generate(name, _table(arity), 40)
        assert narrowed.count("\n") > grown.count("\n"), f"{name}: wrapper never fired"
        return
    pytest.fail(f"{name}: no table up to 4 inputs produced a program long enough")


@pytest.mark.parametrize("name", WRAPPED)
def test_every_wrapper_fires_on_a_template_too(name: str) -> None:
    r"""A parameterized language's *template* must wrap, not just its."""
    example = _example(name)
    if example.fill is None:
        pytest.skip(f"{name} is not parameterized; its template is its program")
    for arity in range(1, 5):
        template = generate(name, _table(arity))
        if "\n" in template or len(template) <= 40:
            continue
        assert generate(name, _table(arity), 40) != template, (
            f"{name}: the wrapper left the template untouched"
        )
        return
    pytest.skip(f"{name}: no table up to 4 inputs gives a template long enough")


@pytest.mark.parametrize("name", WRAPPED)
# part of 6.7s: runs the.
@pytest.mark.medium
def test_no_width_breaks_a_placeholder(name: str) -> None:
    r"""No width may put a line break through the middle of a ``{Xi}``."""
    example = _example(name)
    if example.fill is None:
        pytest.skip(f"{name} is not parameterized; it has no placeholder")
    for arity in range(1, 4):
        template = generate(name, _table(arity))
        placeholders = [f"{{X{i}}}" for i in range(arity) if f"{{X{i}}}" in template]
        for width in range(4, 121):
            wrapped = generate(name, _table(arity), width)
            for placeholder in placeholders:
                assert wrapped.count(placeholder) == template.count(placeholder), (
                    f"{name}: width {width} at {arity} inputs broke {placeholder}"
                )


# Tables the generators take a.
# committed examples are all.
# between them they exercise.
# shape of the program, not by.
# needed a table that puts an.
# AND2 nor parity produces at.
_OTHER_TABLES = {"majority": "00010111", "mixed": "11111001"}

# Long enough that a run which.
# that eight of them are not a.
# one, so a timeout is one of.
# failure -- what must match is.
# the unwrapped one does.
_RUN_TIMEOUT = 5.0


def _behaviour(name: str, program: str, stdin: str) -> str:
    r"""What ``program`` does, as a value: its output, or how it failed."""
    try:
        return run(name, program, stdin, timeout=_RUN_TIMEOUT)
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


@pytest.mark.slow
@pytest.mark.parametrize("name", WRAPPED)
@pytest.mark.parametrize("shape", sorted(_OTHER_TABLES))
def test_wrapping_holds_on_a_table_the_examples_do_not_cover(
    name: str, shape: str
) -> None:
    r"""Wrapping still preserves behaviour on a bigger, differently-shaped."""
    example = _example(name)
    table = _OTHER_TABLES[shape]
    for combo in range(8):
        bits = tuple(int(b) for b in format(combo, "03b"))
        variant = replace(
            example,
            table=table,
            bits=bits if example.fill else (),
            inputs=() if example.fill else tuple(str(b) for b in bits),
        )
        plain = variant.build(width=None)
        wrapped = variant.build(NARROW_WIDTH)
        if wrapped == plain:
            continue
        stdin = "".join(f"{line}\n" for line in variant.inputs)
        assert _behaviour(name, wrapped, stdin) == _behaviour(name, plain, stdin), (
            f"{name}: wrapping changed the answer on the {shape} table, inputs {bits}"
        )


# Tables and widths for the two.
# widths reach well below what.
# narrow end is where a layout.
# width cannot be met, and the.
# widths every program already.
_HONOUR_TABLES = {
    "parity1": "01",
    "parity2": "0110",
    "parity3": "01101001",
    "majority3": "00010111",
}
_HONOUR_WIDTHS = (10, 20, 40, 80)


def _columns(program: str) -> int:
    r"""The width of the widest row of ``program``."""
    return max(len(line) for line in program.split("\n"))


def _laid_out(name: str, table: str, bits: str, width: int | None) -> str:
    r"""``name``'s program for ``table`` and ``bits``, laid out to."""
    example = EXAMPLE_BY_ID[LANGUAGES[name].id]
    variant = replace(
        example,
        table=table,
        bits=tuple(int(bit) for bit in bits) if example.fill else (),
        inputs=() if example.fill else tuple(bits),
    )
    return variant.build(width)


@pytest.mark.parametrize("name", WIDTH_HONOURING)
def test_width_honouring_layout_meets_any_width_it_can(name: str) -> None:
    r"""The layout fits the width whenever the generator can build it that."""
    language = next(lang for lang in LANGUAGES.values() if lang.id == name)
    for label, table in _HONOUR_TABLES.items():
        arity = len(table).bit_length() - 1
        bits = "0" * arity
        narrowest = _columns(_laid_out(language.name, table, bits, 1))
        for width in _HONOUR_WIDTHS:
            columns = _columns(_laid_out(language.name, table, bits, width))
            assert columns <= max(width, narrowest), (
                f"{name}: {label} at width {width} came out {columns} columns, "
                f"wider than both the width and its {narrowest}-column floor"
            )


@pytest.mark.parametrize("name", WIDTH_HONOURING)
# part of 6.7s: runs the.
@pytest.mark.medium
def test_width_honouring_layout_computes_the_same_thing(name: str) -> None:
    r"""Laying the program out to a width does not change what it computes."""
    language = next(lang for lang in LANGUAGES.values() if lang.id == name)
    example = EXAMPLE_BY_ID[language.id]
    relaid = 0
    for label, table in _HONOUR_TABLES.items():
        arity = len(table).bit_length() - 1
        for combo in range(2**arity):
            bits = format(combo, f"0{arity}b")
            # A parameterized generator.
            stdin = "" if example.fill else "".join(f"{bit}\n" for bit in bits)
            compact = _laid_out(language.name, table, bits, None)
            expected = _behaviour(language.name, compact, stdin)
            for width in _HONOUR_WIDTHS:
                folded = _laid_out(language.name, table, bits, width)
                relaid += folded != compact
                assert _behaviour(language.name, folded, stdin) == expected, (
                    f"{name}: laying {label} out to width {width} changed the "
                    f"answer for inputs {bits}"
                )
    # A generator that stopped.
    # assertion above by comparing.
    assert relaid, f"{name}: no width produced a different layout"


@pytest.mark.parametrize("name", sorted(UNWRAPPABLE))
def test_unwrappable_languages_are_untouched(name: str) -> None:
    r"""A language that cannot take newlines ignores the width."""
    language = next(lang for lang in LANGUAGES.values() if lang.id == name)
    assert language.id not in WRAPPERS, UNWRAPPABLE[name]
    program = "iiiioddo"
    assert wrap_program(program, language.id, 4) == program


@pytest.mark.parametrize("name", WIDTH_HONOURING)
def test_width_honouring_languages_respect_the_width(name: str) -> None:
    r"""A generator that lays itself out really does fit the width given."""
    language = next(lang for lang in LANGUAGES.values() if lang.id == name)
    assert language.id not in WRAPPERS, f"{name} both lays out and reflows"
    assert language.boolean is not None
    for width in (40, 80, 94):
        program = generate(language.name, TABLE, width)
        assert max(map(len, program.split("\n"))) <= width
    # omitting the width is still.
    assert generate(language.name, TABLE) == language.boolean(TABLE)


@pytest.mark.parametrize("name", WRAPPED)
def test_no_width_is_unchanged(name: str) -> None:
    r"""Omitting the width reproduces exactly what the generator always."""
    lang = LANGUAGES[name]
    assert lang.boolean is not None
    assert generate(name, TABLE) == lang.boolean(TABLE)


def test_between_is_no_longer_wrapped_and_still_computes_its_table() -> None:
    r"""Between's wrapper went with the text generators that fed it."""
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
    r"""Clockwise honours a width by shaping, never by inserting newlines."""
    assert "clockwise" not in WRAPPERS
    grid = generate("Clockwise", TABLE)
    assert wrap_program(grid, "clockwise", 10) == grid


def test_zero_and_negative_widths_do_not_wrap() -> None:
    r"""A nonsensical width is a no-op rather than an error or a crash."""
    for width in (0, -1):
        assert wrap_program("a b c", "decleq", width) == "a b c"


def test_already_multiline_programs_are_left_alone() -> None:
    r"""A program that already has newlines is never re-wrapped."""
    program = "line one\nline two"
    assert wrap_program(program, "decleq", 4) == program


def test_wrap_tokens_refuses_a_pattern_that_does_not_tile() -> None:
    r"""A pattern that drops characters returns the program unwrapped."""
    assert wrap_tokens("aXbXc", 2, "[abc]") == "aXbXc"


def test_wrap_space_delimited_never_splits_a_token() -> None:
    r"""A token longer than the width gets its own line, unbroken."""
    wrapped = wrap_space_delimited("1 22 333333 4", 3)
    assert "333333" in wrapped.split("\n")
    assert wrapped.replace("\n", " ") == "1 22 333333 4"


def test_polynomial_never_strands_a_sign_on_its_own_line() -> None:
    r"""The raggedness this wrapper exists to fix: a line that is just a."""
    program = generate("Polynomial", TABLE, DEFAULT_WIDTH)
    assert "\n" in program
    assert not [line for line in program.split("\n") if line.strip() in ("+", "-")]


def test_polynomial_starts_a_term_only_on_a_line_of_its_own() -> None:
    r"""The layout: a term starts a line, and only ever at the start of one."""
    program = generate("Polynomial", TABLE, DEFAULT_WIDTH)
    lines = program.split("\n")
    # Line 1 is ``f(x) = <term>``:.
    assert lines[0].startswith("f(x) = ")
    assert len(lines[0].split()) == 3
    for line in lines[1:]:
        # Either a line that starts a.
        # carrying the previous one.
        assert len(line.split()) == (2 if line.startswith(("+ ", "- ")) else 1)


def test_polynomial_carries_a_term_over_without_inventing_a_sign() -> None:
    r"""A row continuing a term is bare: the sign belongs to the term's."""
    program = generate("Polynomial", TABLE, DEFAULT_WIDTH)
    carried = [
        line for line in program.split("\n")[1:] if not line.startswith(("+ ", "- "))
    ]
    assert carried, "the table is too small to fold a term -- pick a wider one"
    assert all(line.strip() and " " not in line for line in carried)


def test_polynomial_wrap_is_undone_by_deleting_whitespace() -> None:
    r"""The wrap only inserts newlines, so the parsed program is unchanged."""
    plain = generate("Polynomial", TABLE)
    wrapped = generate("Polynomial", TABLE, DEFAULT_WIDTH)
    assert wrapped != plain
    assert re.sub(r"\s", "", wrapped) == re.sub(r"\s", "", plain)


def test_polynomial_keeps_the_header_with_the_first_term() -> None:
    r"""``f(x)`` and ``=`` are not terms and do not get lines of their own."""
    assert _polynomial("f(x) = x^2 - 3x + 7", 80).split("\n")[0] == "f(x) = x^2"


def test_polynomial_meets_the_width_it_is_given() -> None:
    r"""Every row fits, at every width -- the coefficients fold too."""
    program = generate("Polynomial", TABLE)
    for width in (13, 40, 80, 200):
        for line in _polynomial(program, width).split("\n"):
            assert len(line) <= width


def test_polynomial_keeps_an_oversized_term_with_its_sign() -> None:
    r"""A term wider than the width keeps its sign rather than shedding it."""
    wrapped = _polynomial("f(x) = x^2 - 123456789x + 7", 12)
    assert "- 123456789x" in wrapped.split("\n")


def test_polynomial_leaves_a_trailing_sign_alone() -> None:
    r"""A sign with no term after it is kept rather than dropped."""
    assert _polynomial("f(x) = x +", 80) == "f(x) = x\n+"


def test_polynomial_keeps_a_sign_with_no_term_to_attach_to() -> None:
    r"""Two signs in a row: the first has no term, and is kept as a line."""
    assert _polynomial("f(x) = x + - 7", 80) == "f(x) = x\n+\n- 7"


def test_pct_header_terminator_matches_the_generator() -> None:
    r""":mod:`wrap` spells %^2^-1's header terminator; the generator owns."""
    from esolangs.tools.boolean.pct_squared_minus_one import _HEADER_END

    assert _PCT_HEADER_END == _HEADER_END


def test_pct_folds_its_header_to_the_width() -> None:
    r"""The header meets the width, at every arity -- it is not kept whole."""
    for arity in (2, 4, 6):
        template = generate("%^2^-1", _table(arity))
        for width in (40, 80):
            wrapped = generate("%^2^-1", _table(arity), width)
            assert _PCT_HEADER_END in wrapped, "the header and body ran together"
            for line in wrapped.split("\n"):
                assert len(line) <= width, f"{arity} inputs, width {width}: {len(line)}"
        assert len(template.split("\n")[0]) > 80 or arity == 2


def test_pct_fill_is_unchanged_by_where_the_header_folded() -> None:
    r"""However the header is folded, the filled program is byte-identical."""
    from esolangs.tools.boolean.pct_squared_minus_one import _HEADER_END, fill

    for arity in (2, 4):
        template = generate("%^2^-1", _table(arity))
        header, _, body = template.partition(_HEADER_END)
        for every in (7, 23, 174, 175):
            refolded = (
                "\n".join(header[i : i + every] for i in range(0, len(header), every))
                + _HEADER_END
                + body
            )
            for combo in range(2**arity):
                bits = [(combo >> (arity - 1 - i)) & 1 for i in range(arity)]
                assert fill(refolded, bits) == fill(template, bits)


def test_wrap_grid_right_aligns_into_columns() -> None:
    r"""Every token is right-aligned in a cell as wide as the widest one."""
    # Cell width 3, so 80 // 4 ==.
    wrapped = wrap_grid("1 22 333 4", 80)
    assert wrapped == "  1  22 333   4"


def test_wrap_grid_columns_line_up_across_rows() -> None:
    r"""The point of the grid: column k starts at the same offset every row."""
    # Six 3-character tokens with.
    # holds "aaa bbb ccc") puts two.
    wrapped = wrap_grid("111 222 333 444 555 666", 11)
    rows = wrapped.split("\n")
    assert rows == ["111 222 333", "444 555 666"]
    starts = [[i for i, ch in enumerate(row) if ch != " "][::3] for row in rows]
    assert starts[0] == starts[1]


def test_wrap_grid_leaves_no_trailing_whitespace() -> None:
    r"""Right-aligning pads on the left, so no line ends in a space."""
    wrapped = wrap_grid("1 22 333 4 5 66", 12)
    for line in wrapped.split("\n"):
        assert line == line.rstrip()


def test_wrap_grid_preserves_the_token_sequence() -> None:
    r"""Padding is whitespace, so the tokens read back exactly."""
    program = "-1 321 3 -1 322 6 1000000000 0 0 48 49"
    assert wrap_grid(program, 40).split() == program.split()


def test_wrap_grid_sizes_cells_to_the_bulk_not_the_outlier() -> None:
    r"""A lone wide token does not pad every other cell out to its width."""
    tokens = ["321"] * 20 + ["1000000000"]
    assert _cell_width(tokens) == 3
    # Without the outlier rule this.
    wrapped = wrap_grid(" ".join(tokens), 80)
    assert wrapped.split("\n")[0] == " ".join(["321"] * 20)


def test_wrap_grid_spans_an_outlier_across_whole_cells() -> None:
    r"""A token too wide for one cell takes several, keeping the lattice."""
    assert _span(10, 3) == 3
    wrapped = wrap_grid("111 222 1000000000 333 444", 80)
    assert wrapped == "111 222  1000000000 333 444"
    # "111 222 " is 8 columns, the.
    # after it starts at column 20.
    assert wrapped.index("333") == 20
    assert wrapped.index("333") % 4 == 0


def test_wrap_grid_never_straddles_a_row_boundary() -> None:
    r"""A spanning token starts a new row rather than breaking across two."""
    # Cell width 2, so three cells.
    # token needs three of them,.
    # "11 22", so it opens the.
    wrapped = wrap_grid("11 22 1234567 33", 11)
    assert wrapped.split("\n") == ["11 22", " 1234567 33"]
    # The token stayed whole --.
    assert "1234567" in wrapped.split("\n")[1]


def test_wrap_chars_breaks_anywhere() -> None:
    r"""The single-character families break at exactly the width."""
    assert wrap_chars("abcdef", 2) == "ab\ncd\nef"


# A three-level nest around a.
# generator emits: each level.
# up before the closers unwind.
_NESTED_BIO = "0ox; 0ix{1ox;0ix{1ox;0oy;};};0oy;0oy;1iy;"


def _bio_tokens(program: str) -> list[str]:
    r"""The commands BIO's own parser keeps, in order."""
    return re.findall(r"[01][oOiI][xXyYzZ](?:\{|;)|\};", program)


def test_bio_indents_a_nested_program_by_depth() -> None:
    r"""Each loop level is two spaces deeper than the one outside it."""
    lines = _bio(_NESTED_BIO, DEFAULT_WIDTH).split("\n")
    indents = [len(line) - len(line.lstrip(" ")) for line in lines]
    assert indents == [0, 2, 4, 2, 0, 0]


def test_bio_keeps_a_brace_with_the_command_that_opens_it() -> None:
    r"""``{`` marks the body of the ``0i?`` before it and never leads a."""
    lines = _bio(_NESTED_BIO, DEFAULT_WIDTH).split("\n")
    assert not any(line.lstrip(" ").startswith("{") for line in lines)
    assert [line for line in lines if line.rstrip().endswith("{")]


def test_bio_indent_preserves_the_command_sequence() -> None:
    r"""Indenting is whitespace only: the parser sees the same commands."""
    wrapped = _bio(_NESTED_BIO, DEFAULT_WIDTH)
    assert _bio_tokens(wrapped) == _bio_tokens(_NESTED_BIO)


def test_bio_leaves_a_flat_program_packed() -> None:
    r"""A program under two levels deep gains no indentation."""
    flat = "0ox;0ix{1ox;0oy;};0oy;1iy;"
    wrapped = _bio(flat, DEFAULT_WIDTH)
    assert not any(line.startswith(" ") for line in wrapped.split("\n"))


def test_bio_packs_a_ramp_to_the_width_at_its_own_indent() -> None:
    r"""A long straight run costs rows at its level, not one long line."""
    program = "0ox;0ix{" + "0oy;" * 40 + "0ix{1ox;};};"
    lines = _bio(program, 20).split("\n")
    assert max(len(line) for line in lines) <= 20
    # The ramp sits inside the.
    # indented rather than only the.
    ramp = [line for line in lines if "0oy" in line]
    assert len(ramp) > 1
    assert all(line.startswith("  ") for line in ramp)


def test_bio_indent_stops_growing_before_it_crowds_the_line() -> None:
    r"""A deep program keeps room to pack, and still unwinds its closers."""
    depth = 40
    program = "0ox;" + "0ix{" * depth + "1ox;" + "};" * depth
    lines = _bio(program, 20).split("\n")
    assert max(len(line) for line in lines) <= 20
    assert _bio_tokens("\n".join(lines)) == _bio_tokens(program)


def test_bio_indent_leaves_no_trailing_whitespace() -> None:
    r"""No line carries the separator the boolean generator writes."""
    wrapped = _bio(_NESTED_BIO, DEFAULT_WIDTH)
    assert all(line == line.rstrip() for line in wrapped.split("\n"))


def test_wrappers_refuse_input_they_do_not_recognize() -> None:
    r"""Each wrapper hands back anything outside the shape it knows."""
    # An empty program has no.
    assert wrap_space_delimited("", 40) == ""
    assert wrap_grid("", 40) == ""
    # BIO's tokens have to tile the.
    # the regex did not account for.
    assert _bio("0ox;!!!", 40) == "0ox;!!!"
    # Taglate needs a queue seed.
    assert _taglate("seed-only", 40) == "seed-only"


def test_polynomial_leaves_a_program_too_short_to_have_a_header() -> None:
    r"""The ``f(x) =`` header is three terms; a shorter program has none."""
    assert _polynomial("1", 10) == "1"


def test_six_five_keeps_an_operand_with_its_command() -> None:
    r"""``7``/``8`` take the next character, so a break never lands between."""
    program = "657812A"
    for width in range(2, 10):
        for line in _six_five(program, width).split("\n"):
            assert not line.endswith(("7", "8")), f"width {width} split an operand"


def test_six_five_keeps_a_guard_with_the_instruction_it_skips() -> None:
    r"""``7n`` skips the next *token*, and a newline is one."""
    program = "70621A"
    unwrapped = _run("6-5", program)
    for width in range(2, 12):
        assert _run("6-5", _six_five(program, width)) == unwrapped


def test_six_five_wrapped_programs_still_run() -> None:
    r"""A wrapped 6-5 program computes what the unwrapped one computed."""
    program = generate("6-5", TABLE)
    unwrapped = _run("6-5", program)
    for width in (3, 5, 8, 13, 40, 60):
        assert _run("6-5", _six_five(program, width)) == unwrapped
