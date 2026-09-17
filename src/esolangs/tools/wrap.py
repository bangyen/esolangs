r"""Wrap generated programs to a readable width, on token boundaries.

The generators emit one long line for most languages -- a Polynomial program
for a dense three-input table is 2471 characters -- and most languages treat
a newline as whitespace or as a comment character, so such a program can be
broken across lines without changing what it does.

The wrapping is *token-aware*, which is the point of this module.  Slicing
every ``width`` characters can split ``-6`` into ``-`` and ``6`` (a load
error in the numeric languages, which is at least loud) or split BIO's
fixed-width ``0ox`` triples so the program still runs and prints garbage
(which is not).  Each wrapper knows what a token is in its family and only
breaks between two of them.

Not every language can take newlines, so wrapping is opt-in per language:

- The 2D languages read newlines as row separators.
- NoComment has no comment syntax at all, so ``\n`` is a load error.
- Forbin and Packlang tolerate reflow but keep their statements on indented
  lines inside braces, so their wrapper folds only a line over the width.

Being unwrappable is not being unbounded.  Twelve generators lay out their
own *shape*, so they honour a width by building a different one rather than
by reflowing: Streetcode, WII2D and LaserFuck fold their runs into a
boustrophedon, COD turns its drawing a quarter turn so the width becomes its
tallest block, Clockwise and Flowchart stack their decision trees a column
to a node, Dig turns its tree round once, Alight steers with ``turn`` and
Super SNUSP with mirrors, function x(y) and the Algebraic Programming
Language *name* their subexpressions so a statement becomes a line each, and
Circuit Diagram bands -- carrying every live signal back to a column near
the left so the ones behind it are freed.  :func:`takes_width` is how a
caller tells; those twelve never reach :func:`wrap_program`.

Ten of the twelve are grids, which :func:`wrap_program` skips for being
already multi-line.  The two naming ones are line-structured source and so
are also in the tests' unwrappable table; the two facts are independent.

Only Clockwise folds to an arbitrary width, and what it trades is rows,
since a stacked level writes the subtree below it twice.  In the others
something cannot move, and a width under that floor returns the narrowest
program rather than refusing: WII2D's junction chain carries one input per
junction, COD's floor is ``2 ** (n + 1) + 1``, Dig's tree can turn round
exactly once, function x(y) floors at one node's line, APL at the prefix
reading its inputs, Flowchart at ``n + 5``, Alight at its ``2 ** n``
table literal, Super SNUSP at four columns, and Circuit Diagram at the rails
and complements every minterm reads, about ``10 * n`` columns.

Wrapping otherwise assumes a single-line program, since a newline already
means layout.  Taglate is the exception -- its first line seeds the queue --
and :data:`MULTILINE` names the languages whose wrappers handle their own
newlines that way.

Most wrappers only decide *where* the newlines go.  Two also place tokens
within a line: :func:`_bio` indents two spaces per loop level, since the
boolean generator nests one loop per row and that telescoping chain is
invisible packed flat, and :func:`wrap_grid` right-aligns into fixed cells,
which lines the columns up between rows of the subleq-family OISCs and makes
a diff of one readable.  Grid layout is opt-in for the same reason wrapping
is: Polynomial is space-delimited too, but its tokens run from 1 to 98
characters.  It gets its own wrapper, which glues each ``+`` or ``-`` to the
term it signs so no line is just a sign.  SLOW ACV MAMMALIAN uses the grid
layout with a fixed four-character cell.

:data:`WRAPPERS` maps a language id to the wrapper it needs; a language
absent from it is not wrapped.  :func:`wrap_program` is the entry point the
generators and the public API call.
"""

import inspect
import re
from collections.abc import Callable

from esolangs.tools.helpers import MARK, MOST_INPUTS, mark

# 80: the conventional review/diff width, close to the repo's 88 for Python.
DEFAULT_WIDTH = 80


def shortest(*candidates: str) -> str:
    """Return the shortest of ``candidates``, preferring the earlier on a tie.

    Several generators can express the same program in more than one shape --
    a ring against a fold, a minterm sum against a decision tree, an absolute
    encoding against a delta one -- and which shape wins depends on the input,
    not on the language.  Rather than predict the winner, those generators
    build every shape and emit the smallest, a rule the test suite pins in
    several places (``test_the_emitted_program_has_an_exact_length`` for
    Streetcode, whose docstring notes nothing else there measures size at
    all, and the ``len(program) <= ...`` bounds in the generator suites).

    This names that rule so a reader meets it as a decision rather than
    re-deriving it from a ``min`` with a ``key``.  Ties keep the first
    argument, so callers should pass the canonical shape first and the output
    stays stable when two shapes come out the same length.
    """
    return min(candidates, key=len)


def wrap_space_delimited(program: str, width: int) -> str:
    """Wrap a whitespace-delimited program, never splitting a token.

    Used by the numeric languages (AddSubJump, Decleq, S*bleq, ...), whose
    programs are runs of signed integers separated by spaces.  A token
    longer than ``width`` is left on its own line rather than broken, since
    breaking it would change the program.
    """
    return _join_tokens(program.split(), width, separator=" ")


def _indented(program: str, width: int) -> str:
    """Wrap each source line separately, preserving its leading indentation."""
    lines: list[str] = []
    for line in program.split("\n"):
        indent = line[: len(line) - len(line.lstrip())]
        content = line[len(indent) :]
        wrapped = wrap_space_delimited(content, max(1, width - len(indent)))
        lines.extend(indent + part for part in wrapped.split("\n"))
    return "\n".join(lines)


def wrap_grid(program: str, width: int) -> str:
    """Wrap a whitespace-delimited program into a right-aligned grid.

    The subleq-family OISCs (AddSubJump, Decleq, S*bleq) are the numeric
    languages whose tokens are all about the same size: an address, an
    operand, a jump target.  Packing those with a single space, the way
    :func:`wrap_space_delimited` does, leaves the columns ragged, so
    nothing lines up between one row and the next even though every row
    holds the same kind of field.  Padding each token to a common cell
    width and right-aligning it inside that cell lines the columns up
    vertically, which makes a diff of one readable: a changed operand
    stays in its column instead of shifting every token after it.

    The cell width is :func:`_cell_width` of the program's own tokens, so
    it follows the program rather than being fixed.  A token too wide for
    one cell spans as many whole cells as it needs (see :func:`_span`)
    instead of pushing the rest of its row out of alignment -- every later
    token on the row still starts on a cell boundary.  Such a token never
    straddles a row boundary; it starts a new row if the current one cannot
    hold its span.

    Right-aligning pads on the left, so no line ever carries trailing
    whitespace.  The interpreters split on whitespace *runs*
    (:func:`~esolangs.interpreters.memory.parse_int_memory`), so the
    padding is invisible to them and the program means exactly what it did
    unpadded.
    """
    tokens = program.split()
    if not tokens:
        return program
    return _wrap_grid(tokens, width, _cell_width(tokens))


def _wrap_grid(
    tokens: list[str], width: int, cell: int, *, left_aligned: bool = False
) -> str:
    """Align ``tokens`` on a lattice whose base cell is ``cell``."""
    # k cells plus k-1 separators.
    per_row = max(1, (width + 1) // (cell + 1))
    lines: list[str] = []
    row: list[str] = []
    used = 0
    for token in tokens:
        span = _span(len(token), cell)
        if row and used + span > per_row:
            lines.append(" ".join(row).rstrip())
            row, used = [], 0
        # k cells plus the k-1 separators it absorbs.
        slot = span * cell + span - 1
        row.append(token.ljust(slot) if left_aligned else token.rjust(slot))
        used += span
    # ``row`` always holds the last row here (empty ``tokens`` returned above).
    if row:  # pragma: no branch - never empty; see above
        lines.append(" ".join(row).rstrip())
    return "\n".join(lines)


def _mammalian(program: str, width: int) -> str:
    """Wrap Mammalian on four-character cells, one cell per ``SEED``.

    ``SEED`` is the construction's unit: it forms nearly all long runs in a
    generated program.  The other command words span two or three cells, so
    every following ``SEED`` returns to the same lattice without padding all
    cells to the longest word.
    """
    tokens = program.split()
    if not tokens:
        return program
    return _wrap_grid(tokens, width, 4, left_aligned=True)


def _cell_width(tokens: list[str]) -> int:
    """Return the cell width the bulk of ``tokens`` fits in.

    The widest token is not always the right cell width.  A program that is
    hundreds of short addresses alongside a handful of much longer ones --
    an out-of-range jump target, a large literal -- would have every cell
    sized to the outlier and the whole file padded out to a few sparse
    columns.  So an outlier is dropped while it is at least twice the next
    distinct width, and the tokens that remain set the width; the dropped
    ones span several cells instead (see :func:`_span`).

    Decleq's boolean program used to be the example here, with four
    ten-character halt sentinels among 321 tokens of three characters or
    fewer; its generator now computes the smallest address that halts, so
    the outlier is gone and that program is a uniform grid.  The rule stays
    because it is not specific to it -- any of the three grid languages can
    emit a token far wider than its neighbours.
    """
    widths = sorted({len(token) for token in tokens}, reverse=True)
    while len(widths) > 1 and widths[0] >= 2 * widths[1]:
        widths.pop(0)
    return widths[0]


def _span(length: int, cell: int) -> int:
    """Return how many whole cells a token of ``length`` characters needs.

    A span of ``k`` cells holds ``k * cell`` characters plus the ``k - 1``
    separators it absorbs, so the token fits when
    ``length <= k * (cell + 1) - 1`` -- hence the ceiling below.
    """
    return max(1, -(-(length + 1) // (cell + 1)))


#: One input's mark run (:func:`~esolangs.tools.helpers.mark`), one token:
#: a break inside would land inside the setter.  Adjacent runs are two tokens.
_RUN = "|".join(f"{re.escape(mark(i))}+" for i in range(MOST_INPUTS))


def wrap_tokens(program: str, width: int, pattern: str) -> str:
    """Wrap a program whose tokens are the matches of ``pattern``.

    Used by the languages with fixed-width multi-character commands, where
    the token boundary cannot be found by looking for whitespace.  The
    pattern must tile the program exactly -- every character belongs to some
    token -- so that rejoining the tokens reproduces the input; a program
    that does not tile is returned unwrapped rather than corrupted.

    A :data:`_RUN` is tried ahead of ``pattern``, so no caller has to
    remember a template's runs.
    """
    tokens = re.findall(f"{_RUN}|{pattern}", program)
    if "".join(tokens) != program:
        return program
    return _join_tokens(tokens, width, separator="")


def wrap_chars(program: str, width: int) -> str:
    """Wrap a program whose every character is its own token.

    The single-character-command families (Brainfuck and its relatives),
    where any position is a legal break -- except inside a template's
    :data:`_RUN`, which is why a template takes the token path.
    """
    if not any(MARK <= ord(c) < MARK + MOST_INPUTS for c in program):
        return "\n".join(program[i : i + width] for i in range(0, len(program), width))
    return _join_tokens(re.findall(f"{_RUN}|[\\s\\S]", program), width, separator="")


def _join_tokens(tokens: list[str], width: int, separator: str) -> str:
    """Pack ``tokens`` into lines of at most ``width`` characters."""
    lines: list[str] = []
    current = ""
    for token in tokens:
        candidate = token if not current else current + separator + token
        if current and len(candidate) > width:
            lines.append(current)
            current = token
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\n".join(lines)


# ``[01][oi][xyz]`` plus ``;`` or ``{``, or ``};``, or the separating
# space.  Varying width is why neither a character wrap nor a fixed stride
# will do.
_BIO_COMMAND = r"[01][oOiI][xXyYzZ](?:\{|;)|\};| "

# Brainfuck-family, plus a digit argument (Dimensional's ``>0``/``<0``).
_DIMENSIONAL_COMMAND = r"[<>]\d+|."

# 6-5's ``7``/``8`` take the next character, whatever it is (the
# interpreter's tokenizer merges the pair blind), so this matches any
# character, not ``[0-9A-Z]``.  ``7n`` also swallows the instruction it
# guards, operand included; see :func:`_six_five`.
_SIX_FIVE_COMMAND = r"7[\s\S](?:[78][\s\S]|[\s\S])|8[\s\S]|[\s\S]"

# Literal-printing languages: a newline inside the literal is printed (or,
# in Sophie, printed instead).  The literal is one token; an over-wide one
# stays on its own line (:func:`_join_tokens`'s oversized-token rule).
# Sophie: ``#\$(\d+)`` numeric load, ``@\$(\d+){`` numeric branch, the
# one-character forms behind them, longest first.  The old ``#\$\d+,``
# required the comma, so ``#$1`` tokenized as ``#$`` + ``1`` and a newline
# between them loaded ``'\n'``.  ``}{`` is an if-close beside an else-open:
# a failed branch tests the *next* character for ``{``, so a newline there
# loses the else.
_SOPHIE_COMMAND = r"@\$\d+\{|@\$?.\{|#\$\d+|#\$?.|\}\{|."

# Minifuck ``[`` skips the next character (``ind + 2``), so a newline
# there is what gets skipped; consecutive ``[`` chain, so the whole run
# stays with the character after it.
_MINIFUCK_COMMAND = r"\[+.|."

# Jaune: operand before operator (``3?``, ``2+``, ``v?``) is the only
# unbreakable unit.  A bare run ``++`` splits harmlessly (1 + 1 = 2).
_JAUNE_COMMAND = r"\d+[-+:?!$@]|v[-+?!@]|."
_BRACKET_LITERAL = r"\[[^\]]*\]|."
_EVAL_UNIT = r'"[^"]*"|\?.|.'


def _bio(program: str, width: int) -> str:
    """Wrap BIO, indenting a nested program by its loop depth.

    A BIO command is a triple with the ``;`` that ends it, or -- for a loop
    -- the triple with the ``{`` that opens its body, so a break by
    character count would split one and the program would no longer load.
    Every break here therefore falls between whole commands.

    The boolean BIO generator separates commands with spaces while the text
    one does not, so a space is one of BIO's tokens here.  A line must not
    start with that separator, so break *before* the command it precedes:
    attaching each space to the following command makes the pair one
    unbreakable token and keeps the newline where a space already was.

    A *nested* program is then laid out by depth rather than packed flat.
    The boolean generator nests one loop per truth-table row (``0ix{1ox
    ... }``), so its program is a telescoping chain whose shape is worth
    seeing; packed to a width it reads as one undifferentiated run.  ``0i?``
    opens a level and ``}`` closes one, so the depth is a running count and
    each line is indented by it.  A flat sequence of depth-1 groups shows
    nothing indented that packing does not, so a program shallower than two
    levels takes the flat path.

    The indent is whitespace *between* commands, which BIO ignores, and no
    break lands inside one -- so an indented program means exactly what the
    packed one did.
    """
    tokens = re.findall(f"{_RUN}|{_BIO_COMMAND}", program)
    if "".join(tokens) != program:
        return program
    merged: list[str] = []
    for token in tokens:
        if token.isspace() and merged:
            merged[-1] += token
        else:
            merged.append(token)
    if _bio_depth(merged) >= 2:
        return _bio_indented(merged, width)
    wrapped = _join_tokens(merged, width, separator="")
    # The newline replaces the trailing separator.
    return "\n".join(line.rstrip(" ") for line in wrapped.split("\n"))


def _bio_opens(token: str) -> bool:
    """Whether ``token`` opens a BIO loop.

    The loop-open command is the ``0i?`` triple *with* the ``{`` that opens
    its body, so the brace is what distinguishes it from the ``0i`` of a
    program that is not BIO at all.
    """
    return token[:2].lower() == "0i" and "{" in token


def _bio_closes(token: str) -> bool:
    """Whether ``token`` closes a BIO loop."""
    return token.startswith("}")


def _bio_depth(tokens: list[str]) -> int:
    """Return the deepest loop nesting ``tokens`` reaches."""
    depth = best = 0
    for token in tokens:
        if _bio_opens(token):
            depth += 1
            best = max(best, depth)
        elif _bio_closes(token):
            depth = max(0, depth - 1)
    return best


def _bio_indented(tokens: list[str], width: int) -> str:
    """Lay BIO out one loop level to a line, indented by depth.

    A loop-open ends its line and opens a level; a close returns to the
    previous one.  The commands between two of those are a straight run --
    the ``0oy`` ramp that tops a register up -- and pack to the remaining
    width like any other wrapped program, so a long ramp costs rows at its
    own indent instead of one very long line.

    A deep enough program would indent its ramp off the right edge, so the
    indent stops growing once it would leave a run less than a quarter of
    the width to pack into: past that point the levels share an indent and
    the ``}`` chain still steps back out.
    """
    lines: list[str] = []
    depth = 0
    run: list[str] = []
    # Two spaces a level, while a run still gets a quarter of the width.
    cap = max(0, (width - width // 4) // 2)

    def flush(at: int) -> None:
        """Emit the pending straight run, indented for depth ``at``."""
        if not run:
            return
        pad = " " * (2 * min(at, cap))
        room = max(width - len(pad), width // 4)
        for line in _join_tokens(run, room, separator="").split("\n"):
            lines.append((pad + line).rstrip(" "))
        run.clear()

    for token in tokens:
        if _bio_opens(token):
            run.append(token)
            flush(depth)
            depth += 1
        elif _bio_closes(token):
            flush(depth)
            depth = max(0, depth - 1)
            run.append(token)
            flush(depth)
        else:
            run.append(token)
    flush(depth)
    return "\n".join(lines)


def _dimensional(program: str, width: int) -> str:
    return wrap_tokens(program, width, _DIMENSIONAL_COMMAND)


def _six_five(program: str, width: int) -> str:
    r"""Wrap 6-5, keeping each ``7n`` and the instruction it guards together.

    6-5 is *almost* a single-character language, which is why it used to wrap
    with :func:`wrap_chars`.  Two things make a plain character wrap wrong,
    and the second is why the tokens here are not merely ``7n``/``8n``:

    - ``7`` and ``8`` take the *next character* as their operand, and the
      interpreter merges the pair without inspecting it.  A break between
      them makes the newline the operand (``num("\n")`` is -45, a value no
      cell can equal) and promotes the real operand to an instruction.
    - ``7n`` skips *the next token*, and a newline is itself a token.  A
      break between a ``7n`` and the instruction it guards makes the skip
      consume the newline, so the guarded instruction runs either way --
      ``706A`` leaves cell 0, but ``70\n6A`` leaves cell 6.

    So a ``7n`` binds to whatever follows it, and that three-character group
    is the unbreakable token.  ``8n`` needs no such pairing: its jump finds
    the n-th ``4`` by counting markers, which newlines do not disturb.
    """
    return wrap_tokens(program, width, _SIX_FIVE_COMMAND)


def _sophie(program: str, width: int) -> str:
    """Wrap Sophie, keeping each ``#<char>,`` command whole.

    Sophie prints the character *after* the ``#`` literally, so a break
    between the two makes the newline the argument: the program prints a
    newline where that character should have gone and the intended one is
    lost.  The output stays the same length, which makes this the quiet
    failure of the group -- ``Hello, World!`` came back as ``Hello, Worll!``
    rather than as anything that looked wrong.
    """
    return wrap_tokens(program, width, _SOPHIE_COMMAND)


def _minifuck(program: str, width: int) -> str:
    """Wrap Minifuck, keeping a ``[`` run with the character it may skip.

    ``[`` skips the next instruction when its flipped bit is zero, and the
    interpreter spells that as a cursor advance of two *characters* -- so it
    skips whatever sits there, a newline included.  Put one after a ``[``
    and the ``[`` consumes it, leaving the instruction it was meant to skip
    to run.

    A run of ``[`` chains the displacement, which is why the rule covers the
    whole run rather than a single one: in ``[[x`` a break before ``x`` is
    unsafe even though the character after the *last* ``[`` is not a
    newline, because the first ``[`` can skip the second and land the cursor
    past where the program used to end.
    """
    return wrap_tokens(program, width, _MINIFUCK_COMMAND)


def _bitdeque(program: str, width: int) -> str:
    r"""Wrap Bitdeque, keeping each ``GOTO`` with the operand it jumps to.

    Bitdeque is space-delimited, but its parser spells the jump
    ``GOTO *(\d+)`` -- spaces between the two, not whitespace -- so a break
    that puts ``GOTO`` at the end of one line and ``26`` at the start of the
    next stops matching as a jump.  The token *sequence* is untouched, which
    is why the generic space wrapper looked right: what changes is only
    which characters sit between two tokens, and for this one language that
    is the difference between a jump and something else.

    The effect is silent -- the boolean program answers 1 where it should
    answer 0 -- and positional, so it appears at widths 12 and 13 and not at
    11, 14 or anything wider, a span the conventional 40 and 80 never reach.
    """
    tokens: list[str] = []
    for token in program.split():
        if tokens and tokens[-1] == "GOTO":
            tokens[-1] = f"GOTO {token}"
        else:
            tokens.append(token)
    return _join_tokens(tokens, width, separator=" ")


def _jaune(program: str, width: int) -> str:
    """Wrap Jaune, keeping each operand attached to the operator it feeds.

    Jaune writes an operand before its operator, so ``3?`` is a jump to
    label 3 and ``12+`` adds twelve.  A character wrap that lands between
    the two leaves a bare ``?``, which is a command needing a number and so
    a load error -- loud, unlike Sophie's.  What makes it worth a pattern
    rather than a narrower width is that the break is *positional*: the
    boolean programs survive a wrap at 40 and 80 and fail at 10, 17, 25, 37
    and 50, so a suite testing only the two conventional widths reports a
    wrapper that works.
    """
    return wrap_tokens(program, width, _JAUNE_COMMAND)


def _bracket_literal(program: str, width: int) -> str:
    """Wrap 3x and Modulous, keeping a bracketed group whole.

    Both print through a literal delimited by brackets -- 3x's whole program
    is ``[text]`` and Modulous pushes ``[PSH STR "..."]`` -- so a newline
    inside the brackets is a character the program prints.
    """
    return wrap_tokens(program, width, _BRACKET_LITERAL)


def _quote_literal(program: str, width: int) -> str:
    """Wrap Eval, keeping literals and conditional commands whole."""
    return wrap_tokens(program, width, _EVAL_UNIT)


def _polynomial(program: str, width: int) -> str:
    """Lay a Polynomial program out one signed term to a line.

    Polynomial's terms are space-delimited, so :func:`wrap_space_delimited`
    would wrap it -- but the ``+`` and ``-`` between two terms are tokens of
    their own, and once the terms grow wider than the width every one of
    those signs lands alone on its own line.  A dense table's program
    wrapped into forty lines alternating a hundred-character coefficient
    with a single ``+``, the raggedest possible reading of a polynomial.

    Keeping each sign with the term it signs fixes that much, and packing
    the resulting pairs to a width would be the obvious next step.  This
    wrapper does not: a packed line holds however many terms happen to fit
    -- five, then two, then three -- so its breaks fall where the arithmetic
    lands rather than anywhere meaningful.  One term to a line makes every
    line the same kind of thing and the descending exponents a column you
    can read down, the layout a polynomial is written in by hand.  It is the
    same judgement the module docstring records for Forbin: a language whose
    own idiom is one-item-per-line is left that way rather than packed.

    A term can outrun any width on its own, though -- a single coefficient
    is 5950 digits on the dense eight-input table -- so one term to a line
    is a layout, not yet a width.  The term is folded too, so the width is
    met: 5954 columns become 80.

    Folding *inside* a number is safe here, which is the part worth being
    explicit about: the interpreter's ``_parse_program`` deletes every
    character that is not a digit or one of its few operators from the
    source before it parses, a newline included, so the halves of a split
    number are one number again.  It is not that the digits are re-joined
    by luck -- they are never separate.  The same pass is what makes the
    existing one-term-a-line layout legal, so this only carries the rule
    further in.

    The ``int`` digit-cap derivation does not trip over this either, though
    it looks like it should: ``sanitize`` sizes the cap from the longest
    digit run it can see, and a fold splits those runs -- but
    ``_parse_program`` hands it the *cleaned* text, in which the runs are
    already whole.  Checked by parsing a dense eight-input table folded and
    unfolded and comparing the coefficients, since no small table comes
    near the 4300-digit default cap.

    The header stays with the first term so ``f(x)`` and ``=`` do not become
    lines of their own.

    Discarding every newline and space reproduces what the interpreter
    parses, so the program is unchanged.
    """
    terms: list[str] = []
    pending = ""
    for token in program.split():
        if token in ("+", "-"):
            # A held sign with no term becomes its own line; ``format_coeffs``
            # never emits two in a row, so this only keeps the helper total.
            if pending:
                terms.append(pending)
            pending = token
        elif pending:
            terms.append(f"{pending} {token}")
            pending = ""
        else:
            terms.append(token)
    if pending:
        terms.append(pending)
    # ``f(x)``, ``=`` and the leading term are three tokens of one line.
    if len(terms) >= 3 and terms[0] == "f(x)" and terms[1] == "=":
        terms[:3] = [" ".join(terms[:3])]
    return "\n".join(_folded_term(term, width) for term in terms)


def _folded_term(term: str, width: int) -> str:
    """Break one Polynomial term across rows of at most ``width``.

    The rows are not indented, though an indent would mark a continuation
    nicely: it would be *invented* whitespace, and the suite's restoration
    invariant is that deleting what the wrapper inserted gives the program
    back.  A row that carries a number over is told from a row that starts a
    term by the sign, which only the second has.
    """
    rows = [term[i : i + width] for i in range(0, len(term), max(1, width))]
    return "\n".join(rows)


def _taglate(program: str, width: int) -> str:
    """Wrap Taglate's commands, leaving its queue-seed line alone.

    Taglate is the one wrapped language whose program is already two lines:
    the first seeds the queue and the rest are commands, and the interpreter
    joins everything after that first line before tokenizing.  So the seed
    is structural and must stay on its own row -- wrapping it would feed the
    queue different characters -- while the command text below it breaks
    anywhere, a two-character ``gy``/``gz`` included.
    """
    seed, _, commands = program.partition("\n")
    if not commands:
        return program
    return seed + "\n" + wrap_chars(commands.replace("\n", ""), width)


# %^2^-1's commands are single characters.
_PCT_COMMAND = r"."


# Blank line between a %^2^-1 setter header and body.  Spelled, not
# imported, to keep ``esolangs.tools`` out of a stdlib-only module; a test
# asserts the copies agree.
_PCT_HEADER_END = "\n\n"


def _pct_squared_minus_one(program: str, width: int) -> str:
    """Wrap %^2^-1: the setter-declaration header as well as the body.

    A %^2^-1 *template* is a header of ``0=zero|one;1=...`` declarations, a
    blank line, and the body; ``fill`` reads the declarations out of the
    header, discarding its newlines first, and never shows the interpreter
    any of it.  So the header folds by character -- a declaration is 175
    characters and does not shrink with ``n``, so folding only between two
    would leave a 175-column floor -- and the body wraps by command.  A
    filled program has no header and folds entirely.
    """
    header, blank, body = program.partition(_PCT_HEADER_END)
    if not blank:
        return wrap_tokens(program, width, _PCT_COMMAND)
    flat = header.replace("\n", "")
    folded = "\n".join(flat[i : i + width] for i in range(0, len(flat), width))
    return folded + blank + wrap_tokens(body.replace("\n", ""), width, _PCT_COMMAND)


def _qoibl(program: str, width: int) -> str:
    """Wrap Qoibl, folding each of its lines but keeping them apart.

    A Qoibl program is one statement a line and each statement is
    space-separated tokens -- and a newline between two tokens is just
    whitespace, which is what lets this fold at all.  Every space on a line
    may become a break and the program still computes the same thing;
    measured, not assumed.

    So each line folds on its own with :func:`wrap_space_delimited`, rather
    than the whole program being re-flowed as one stream.  Joining the
    statements first would fold *across* them, and while the language would
    not notice, the reader would: the one-statement-a-line shape is the only
    structure the text has.
    """
    return "\n".join(wrap_space_delimited(line, width) for line in program.split("\n"))


# Language id -> wrapper.  Absent = never wrapped: semantic newlines (2D
# grids), rejects them (NoComment), or position-dependent (ROTfuck).  See
# the module docstring.
WRAPPERS = {
    "addsubjump": wrap_grid,
    "decleq": wrap_grid,
    "sbleq": wrap_grid,
    # Space wrap stranded every sign alone; keep sign with term, one per line.
    "polynomial": _polynomial,
    # Space-delimited, but ``GOTO`` and its target must stay on one line.
    "bitdeque": _bitdeque,
    "bio": _bio,
    "dimensional": _dimensional,
    # 7n/8n are two-character tokens; see :func:`_six_five`.
    "six_five": _six_five,
    "brainfuck": wrap_chars,
    "three_d_brainfuck": wrap_chars,
    "circlefuck": wrap_chars,
    # ``[`` skips the character after it.
    "minifuck": _minifuck,
    "factor": wrap_chars,
    "home_row": wrap_chars,
    "painfuck": wrap_chars,
    "bit_tilde": wrap_chars,
    "unsquare": wrap_chars,
    "rotfuck": wrap_chars,
    "bfstack": wrap_chars,
    "suffolk": wrap_chars,
    # The trailing ``1`` is a terminator, not a structural line.
    "one_two_three": wrap_chars,
    # Four-character cells align the ``SEED`` runs; longer words span cells.
    "slow_acv_mammalian": _mammalian,
    # Multi-character tokens (``vs``, ``0b1``, ``L C 19``); space is the
    # only safe break.
    "lamfunc": wrap_space_delimited,
    "ram0": wrap_space_delimited,
    # Operand-before-operator, so a break between the two is a load error.
    "jaune": _jaune,
    # Print through a literal that must not be broken.
    "modulous": _bracket_literal,
    "eval": _quote_literal,
    "sophie": _sophie,
    "three_x": _bracket_literal,
    "forth": wrap_chars,
    # Both concatenate before tokenizing (Taglate after the queue seed; A
    # Painter Ant drops whitespace), so no break can land inside a command.
    "taglate": _taglate,
    "a_painter_ant": wrap_chars,
    # Longest line in the corpus (2444 columns at n=3); structural header.
    "pct_squared_minus_one": _pct_squared_minus_one,
    "bf_pda": wrap_chars,
    # One statement a line; each folds on its own.
    "qoibl": _qoibl,
    # Generators emit indented blocks; fold only an over-wide line.
    "forbin": _indented,
    "packlang": _indented,
}


# Wrappers that handle a multi-line program themselves instead of being
# skipped: Taglate's first line seeds its queue (kept whole); %^2^-1's
# setter header folds by character; Qoibl's every line is a statement,
# folded separately for the reader (the language would not notice).
MULTILINE = frozenset(
    {"taglate", "pct_squared_minus_one", "qoibl", "forbin", "packlang"}
)


def takes_width(fn: Callable[..., str]) -> bool:
    """Whether a generator lays its own program out to a width.

    Such a generator accepts a second ``width`` parameter and is handed the
    width directly; the rest produce a program that :func:`wrap_program`
    reflows after the fact.  The distinction matters most for a generator
    whose output is a *grid*: reflowing cannot help there, because
    :func:`wrap_program` leaves an already-multi-line program alone.
    """
    try:
        return "width" in inspect.signature(fn).parameters
    except (TypeError, ValueError):  # pragma: no cover - builtins have no signature
        return False


def wrap_program(program: str, language_id: str, width: int | None) -> str:
    """Return ``program`` wrapped to ``width`` columns, if that is possible.

    ``width`` of ``None`` means "do not wrap" and returns the program
    unchanged, which is the default everywhere: wrapping is opt-in, so the
    generators keep producing exactly what they produced before unless a
    caller asks for a width.

    A language that cannot take newlines is returned unchanged rather than
    raising, so a caller can pass one width across every language without
    special-casing the handful of exclusions.  Likewise a program that is
    already multi-line is left alone -- for the 2D and line-oriented
    languages a newline is layout, so reflowing one would move code to
    another row.  The exception is a wrapper in :data:`MULTILINE`, which
    knows which of its program's lines are structural and wraps the rest.
    """
    if width is None or width <= 0:
        return program
    if "\n" in program and language_id not in MULTILINE:
        return program
    wrapper = WRAPPERS.get(language_id)
    if wrapper is None:
        return program
    return wrapper(program, width)
