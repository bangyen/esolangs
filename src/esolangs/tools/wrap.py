r"""Wrap generated programs to a readable width, on token boundaries.

The generators emit one long line for most languages: a Polynomial program
for a dense three-input table is 2471 characters, which no diff or review
pane shows usefully.  Since most languages treat a newline as whitespace
(or as a comment character), such a program can be broken across lines
without changing what it does.

The wrapping is *token-aware*, which is the whole point of this module.
Slicing a program every ``width`` characters is wrong for any language
whose tokens are longer than one character: it can split ``-6`` into ``-``
and ``6`` (a load error in the numeric languages, which is at least loud),
or split BIO's fixed-width ``0ox`` triples so the program still runs and
prints garbage (which is not).  Each wrapper here knows what a token is in
its family and only ever breaks between two of them.

Not every language can take newlines, so wrapping is opt-in per language
rather than a blanket post-processing pass:

- The 2D languages (Dig, WII2D, and the other grid interpreters) read
  newlines as row separators, so a newline moves code to another row.
- NoComment has no comment syntax at all -- an unrecognized character is a
  load error, and that includes ``\n``.
- Forbin would tolerate a reflow -- its interpreter reads whitespace, not
  lines -- but its ``out`` statements sit one per line inside a ``main {}``
  block, and that layout is how the language is meant to be read.  Packing
  them to a width costs more than the ragged right edge it saves, so a
  language whose own idiom is one-statement-per-line is left alone even
  when reflowing it would be safe.
- Basicfuck is excluded for the same reason as Forbin rather than a
  semantic one, and the distinction is worth recording because its
  *program* does not reflow while its *body* does.  Its first two lines are
  structural -- the ``#basicfuck`` directive and the ``#allocate`` list are
  read by position -- but everything below them is whitespace-delimited
  source that packs to a width and still runs, verified on both committed
  examples down to 20 columns.  Only whole tokens may move: ``wrap_chars``
  splits ``write <- X`` and the program stops loading, so this would be a
  :data:`MULTILINE` wrapper over :func:`wrap_space_delimited`, not the
  character one.  It stays unwrapped because packing ``X += Y`` and
  ``while (X) { ... }`` into dense rows is minification of a structured
  source language, the opposite of the readability wrapping exists to serve.
  A ``//`` comment is not the obstacle it looks like either: it packs as a
  single token that forces its line to end there, which is what it already
  does, and comment text too long for one line splits across several, each
  re-prefixed with ``//``.  Verified with comments injected into the
  committed example down to 30 columns.  So nothing mechanical stands in the
  way -- the exclusion is a readability judgement about minifying source,
  and only that.
- MyScript builds its output from string literals like the languages
  :data:`_QUOTE_LITERAL` covers, but its boolean program's newlines are
  structural (its blocks are indented and its interpreter reads them), so it
  cannot be wrapped by making the literal one token the way Eval is.  It is
  excluded until a wrapper understanding its block layout exists; being safe
  today only because its programs come out under one line is not the same as
  being wrappable.

ROTfuck used to belong on that list: its interpreter rotated the program on
*every* character the pointer passed, comments included, so an inserted
newline shifted every later command along the cycle.  That was a deviation
from the wiki ("every time an instruction is executed"), since a comment is
not an instruction; with it fixed, comments are transparent and ROTfuck
wraps like any other single-character-command language.

Being unwrappable is not the same as being unbounded, though.  A generator
that lays out its own *shape* can honour a width by building a different
shape, which no after-the-fact reflow can do: Streetcode folds its
instruction line into a boustrophedon, LaserFuck steers the beam down and
back so a straight run of tape commands costs rows instead of columns,
WII2D folds the run that shifts its answer to an ASCII digit the same way,
COD turns its whole drawing a quarter turn -- its blocks are joined left to
right, so the width becomes the *tallest* block rather than the widest, and
what was the width becomes height, which costs nothing -- Clockwise stacks
the shallow levels of its
decision tree so a branch costs one column instead of the ``2 ** (n -
bit)`` it displaces, Dig turns its tree round once so the deep levels run
back west over the columns the shallow ones used, and function x(y) and the
Algebraic Programming Language both *name* their subexpressions -- the one
binding subtrees to ``var``s, the other minterms to nullary functions -- so
what was a single statement becomes one statement a line.  Flowchart stacks
its drawn tree the way Clockwise stacks its ring, putting every node on one
column, Alight steers its walk into a boustrophedon with ``turn``, and
Super SNUSP does the same with mirrors -- ``\`` and ``/`` stacked in pairs,
which turn a row round in one row and one column, the cheapest fold here.
Circuit Diagram *bands*: every signal still live is carried back to a column
near the left and the columns behind it are freed, which is the only way a
drawing whose gates must each sit right of their inputs can stop growing.
Those twelve generators take the width themselves -- :func:`takes_width` is
how the callers tell -- and never reach :func:`wrap_program`.

Ten of the twelve are grids, which :func:`wrap_program` would skip anyway
for being already multi-line.  The two naming ones are not: they are
line-structured source, so they are *also* in the tests' unwrappable table.
The two facts are independent -- a finished line of either still must not
be broken, and the generator narrows by emitting different lines rather
than by folding the ones it has.

Only Clockwise folds to an arbitrary width; in the others something cannot
move.  WII2D's junction chain carries one input per junction with a detour
row beneath it, so only the decode's tail folds; COD's floor is its tallest
block once the drawing is turned a quarter turn, ``2 ** (n + 1) + 1``; and
Dig's tree can
turn round exactly once, since two bands running the same way would share
the column offsets the turn exists to keep apart; function x(y) floors at
one node's own line, ``var tN: (bK == "1")<tA, tB>``; APL floors at the
prefix that reads its inputs, which cannot be split and grows with ``n``;
Flowchart floors at ``n + 5``, one column of corridor per level beside the
spine; Alight floors at its table literal, ``2 ** n`` characters that are
one token of one command; Super SNUSP floors at four columns, since every
one of its tokens is a single cell but the ``48`` its decode leans on; and
Circuit Diagram floors at what a band cannot reclaim -- the rails and the
complements, read by every minterm and so live for the whole drawing, about
``10 * n`` columns.  A width under the floor returns the narrowest program
rather than refusing.

What Clockwise trades is rows: a stacked level writes the subtree below it
twice over, so each one doubles the program's height.  Its own fold --
collapsing a subtree whose rows all agree -- narrows with the *table*
instead, and the two are independent.

Wrapping otherwise assumes a single-line program, since a newline in one
already means layout.  Taglate is the exception: its first line seeds the
queue and the rest are commands, so its wrapper keeps that seed on its own
row and folds only what follows.  :data:`MULTILINE` names the languages
whose wrappers handle their own newlines that way.

Most wrappers only decide *where* the newlines go.  Two also decide where
the tokens sit within a line, each following the shape its language's
programs actually have.  :func:`_bio` indents a nested BIO program two
spaces per loop level, since the boolean generator nests one loop per
truth-table row and that telescoping chain is invisible packed flat; a
program under two levels deep is packed as before, since indenting a flat
run shows nothing.  :func:`wrap_grid`
right-aligns into columns instead: the subleq-family OISCs (AddSubJump,
Decleq, S*bleq) have uniform-width numeric tokens, so padding each into a
cell and right-aligning it lines the columns up between rows, which makes a
diff of one readable.  It is opt-in for the same reason wrapping is --
Polynomial is space-delimited too, but its tokens run from 1 to 98
characters, and padding those to a common width would be nonsense.
Polynomial gets its own wrapper for a related reason: its one-character
tokens are the ``+`` and ``-`` between terms, and :func:`_polynomial` glues
each to the term it signs so no line is just a sign.  That wrapper then puts
one term to a line rather than packing them to the width, for the reason its
docstring gives.

:data:`WRAPPERS` maps a language id to the wrapper it needs; a language
absent from it is not wrapped.  :func:`wrap_program` is the entry point the
generators and the public API call.
"""

import inspect
import re
from collections.abc import Callable

# The default width for a.
# and diff width, and matches.
# closely enough that a wrapped.
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
    cell = _cell_width(tokens)
    # A row of k cells is k cells.
    per_row = max(1, (width + 1) // (cell + 1))
    lines: list[str] = []
    row: list[str] = []
    used = 0
    for token in tokens:
        span = _span(len(token), cell)
        if row and used + span > per_row:
            lines.append(" ".join(row))
            row, used = [], 0
        # A token spanning k cells is.
        # its k cells plus the k-1.
        row.append(token.rjust(span * cell + span - 1))
        used += span
    # The loop ends by appending,.
    # ``row`` always holds the last.
    if row:  # pragma: no branch - never empty; see above
        lines.append(" ".join(row))
    return "\n".join(lines)


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


# : A ``{Xi}`` placeholder is.
# : ``BooleanExample.fill``.
# : middle leaves it unfilled.
# :.
# : This belongs here rather.
# : property of the templates,.
# : per-pattern is what let it.
# : a ``.`` alternative tiles a.
# : tokens still cover the.
# : break it in half.
# :.
# : A *filled* program has no.
# : one; it only ever applies.
_PLACEHOLDER = r"\{X\d+\}"


def wrap_tokens(program: str, width: int, pattern: str) -> str:
    """Wrap a program whose tokens are the matches of ``pattern``.

    Used by the languages with fixed-width multi-character commands, where
    the token boundary cannot be found by looking for whitespace.  The
    pattern must tile the program exactly -- every character belongs to some
    token -- so that rejoining the tokens reproduces the input; a program
    that does not tile is returned unwrapped rather than corrupted.

    A :data:`_PLACEHOLDER` is tried ahead of ``pattern``, so no caller has to
    remember to spell one out.  Alternation is ordered and anchored at each
    position, so this only wins where a placeholder actually begins: a
    command that merely happens to carry a ``{`` still matches its own
    alternative.
    """
    tokens = re.findall(f"{_PLACEHOLDER}|{pattern}", program)
    if "".join(tokens) != program:
        return program
    return _join_tokens(tokens, width, separator="")


def wrap_chars(program: str, width: int) -> str:
    """Wrap a program whose every character is its own token.

    The single-character-command families (Brainfuck and its relatives),
    where any position is a legal break -- except through a
    :data:`_PLACEHOLDER`, which is why a template takes the token path.  The
    slice below is the same packing for single-character tokens and stays
    the path for the programs that have no placeholder to protect.
    """
    if "{X" not in program:
        return "\n".join(program[i : i + width] for i in range(0, len(program), width))
    tokens = re.findall(f"{_PLACEHOLDER}|[\\s\\S]", program)
    return _join_tokens(tokens, width, separator="")


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


# A BIO command is a.
# it, a loop-open triple.
# ``};`` that closes one --.
# commands with.
# count, and their varying.
# .
# ``{Xi}`` is here because BIO.
# :func:`~esolangs.generate` is.
# and all.
# took its "I cannot read this,.
# silent no-op on every.
# as wrapped.
# .
# It stays spelled out here,.
# :func:`_bio` tokenizes with.
# :func:`wrap_tokens` -- so it.
# and dropping this alternative.
_BIO_COMMAND = r"[01][oOiI][xXyYzZ](?:\{|;)|\};|\{X\d+\}| "

# Brainfuck-family.
# extend them with a digit.
_DIMENSIONAL_COMMAND = r"[<>]\d+|."

# 6-5's ``7``/``8`` take the.
# is -- the interpreter's own.
# it, so the operand is not.
# names.
# wrapper's token stream.
# including ones carrying.
# .
# ``7n`` additionally swallows.
# instruction's own operand.
# newline between them would be.
_SIX_FIVE_COMMAND = r"7[\s\S](?:[78][\s\S]|[\s\S])|8[\s\S]|[\s\S]"

# The languages that print.
# inside the literal is not.
# program goes on to print (or,.
# one that was there).
# token and leaves every other.
# which carry no literal --.
# .
# A literal wider than the.
# broken, which is.
# oversized token: a 3x program.
# over-wide line is the honest.
# program that prints something.
# Sophie's loads and branches.
# matches each as one unit:.
# for a numeric branch, and the.
# alternatives below are those.
# land inside a number or.
# .
# The earlier pattern spelled.
# which is a different command.
# one-character form, tokenized.
# them left a load of the.
# ``}{`` is the last.
# if-block's close beside its.
# the close and then tests.
# whether an else-block.
# else.
# was not opening an else.
_SOPHIE_COMMAND = r"@\$\d+\{|@\$?.\{|#\$\d+|#\$?.|\}\{|."

# A collapsed Minifuck ``[``.
# advances ``ind + 2``), so a.
# the instruction it should.
# chain that displacement, so a.
# after it rather than just the.
_MINIFUCK_COMMAND = r"\[+.|."

# Jaune's operators take an.
# ``2+`` adds 2, and ``v`` is a.
# input names.
# command (``++``) is a counted.
# adding 1 twice is adding 2 --.
_JAUNE_COMMAND = r"\d+[-+:?!$@]|v[-+?!@]|."
_BRACKET_LITERAL = r"\[[^\]]*\]|."
_QUOTE_LITERAL = r'"[^"]*"|.'


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
    tokens = re.findall(_BIO_COMMAND, program)
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
    # A break after a command.
    # line; the newline separates.
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
    # Two spaces a level, up to the.
    # of the width to pack into.
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
    """Wrap Eval, keeping a double-quoted literal whole."""
    return wrap_tokens(program, width, _QUOTE_LITERAL)


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
            # A sign already held has no.
            # own line rather than dropping.
            # emits two in a row (it.
            # is only about the helper.
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
    # ``f(x)``, ``=`` and the.
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


# %^2^-1's commands are single.
# :data:`_PLACEHOLDER`'s.
_PCT_COMMAND = r"."

# What divides a %^2^-1.
# so that a single newline.
# .
# Spelled here rather than.
# ``esolangs.tools.boolean``.
# module that otherwise needs.
# owns the value.
# two agree, so the duplication.
_PCT_HEADER_END = "\n\n"


def _pct_squared_minus_one(program: str, width: int) -> str:
    """Wrap %^2^-1: fold the setter-declaration header as well as the body.

    A %^2^-1 *template* is a header of ``0=zero|one;1=...`` declarations, a
    blank line, and the body.  ``fill`` reads the declarations out of the
    header and substitutes them into the body.

    The header used to be left on one row, on the grounds that it was
    "structural".  It is not the *language's* structure -- the interpreter
    never sees a header, ``fill`` consumes it -- so what kept it whole was
    our own template format, and the format changed: the header is
    terminated by a blank line, and ``fill`` discards the header's newlines
    before reading it.  So the header folds, and 1407 columns at eight
    inputs become the width asked for.

    It folds at a ``;`` where it can, so a row holds whole declarations, and
    *inside* one where it must.  The second case is not an edge: one
    declaration is 175 characters and does not shrink with ``n``, so
    breaking only between declarations would leave a 175-column floor
    whatever the width.

    A *filled* program has no header at all and folds entirely.  Both shapes
    arrive here: :func:`~esolangs.generate` wraps the template, and the
    committed examples wrap what ``fill`` returns.

    The commands are single characters, so the only unbreakable unit is a
    ``{Xi}`` placeholder in an unfilled template.
    """
    header, blank, body = program.partition(_PCT_HEADER_END)
    if not blank:
        return wrap_tokens(program, width, _PCT_COMMAND)
    folded = _pct_header(header.replace("\n", ""), width)
    return folded + blank + wrap_tokens(body.replace("\n", ""), width, _PCT_COMMAND)


def _pct_header(header: str, width: int) -> str:
    """Fold a %^2^-1 header, preferring a break between two declarations.

    Each declaration carries the ``;`` that ends it, so the units pack like
    any other token; a unit too wide for the line is then folded by
    character, which is safe because ``fill`` strips the header's newlines
    before it reads.
    """
    units = [unit + ";" for unit in header.split(";")]
    units[-1] = units[-1][:-1]  # the last declaration has no.
    rows: list[str] = []
    for row in _join_tokens(units, width, separator="").split("\n"):
        rows.append(row if len(row) <= width else wrap_chars(row, width))
    return "\n".join(rows)


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


# Language id -> the wrapper.
# is never wrapped: either its.
# languages), it rejects them.
# model makes character.
# docstring for why each.
WRAPPERS = {
    "addsubjump": wrap_grid,
    "decleq": wrap_grid,
    "sbleq": wrap_grid,
    # Space-delimited, but its.
    # terms outgrow any width, so.
    # sign on a line by itself;.
    # term and gives each term a.
    "polynomial": _polynomial,
    # Space-delimited, but ``GOTO``.
    "bitdeque": _bitdeque,
    "bio": _bio,
    "dimensional": _dimensional,
    # Almost single-character, but.
    # plain character wrap splits.
    "six_five": _six_five,
    "brainfuck": wrap_chars,
    "three_d_brainfuck": wrap_chars,
    "circlefuck": wrap_chars,
    # Not single-character after.
    "minifuck": _minifuck,
    "factor": wrap_chars,
    "home_row": wrap_chars,
    "painfuck": wrap_chars,
    "bit_tilde": wrap_chars,
    "unsquare": wrap_chars,
    "rotfuck": wrap_chars,
    "bfstack": wrap_chars,
    "suffolk": wrap_chars,
    # 123 is single-character.
    # terminator, not a structural.
    "one_two_three": wrap_chars,
    # SLOW ACV MAMMALIAN's commands.
    # ``DIGEST``), so it wraps on.
    # breaking by character count.
    "slow_acv_mammalian": wrap_space_delimited,
    # Space-delimited too, and the.
    # ``vs``/``vg``/``0b1`` and.
    # character tokens that a.
    # instruction indices, which a.
    "lamfunc": wrap_space_delimited,
    "ram0": wrap_space_delimited,
    # Operand-before-operator, so a.
    "jaune": _jaune,
    # Their programs are single.
    # print through a literal that.
    # wrappers above are what keeps.
    "modulous": _bracket_literal,
    "eval": _quote_literal,
    "sophie": _sophie,
    "three_x": _bracket_literal,
    # Forth's commands are single.
    "forth": wrap_chars,
    # Both concatenate their.
    # can never land inside a.
    # queue seed and only then.
    # cannot be split across rows),.
    # outright.
    # need this.
    "taglate": _taglate,
    "a_painter_ant": wrap_chars,
    # Its body is the longest.
    # ``n == 3`` -- and its header.
    "pct_squared_minus_one": _pct_squared_minus_one,
    # Single-character stack.
    # token, so any position is a.
    "bf_pda": wrap_chars,
    # One statement a line, each of.
    # between two tokens is just.
    "qoibl": _qoibl,
}


# The languages whose wrapper.
# rather than being skipped by.
# it.
# wrapper keeps that row whole.
# %^2^-1's first line declares.
# reason, being what ``fill``.
# Qoibl is multi-line for a.
# but every one is a statement,.
# than reflowing the program as.
# the difference -- a newline.
MULTILINE = frozenset({"taglate", "pct_squared_minus_one", "qoibl"})


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
