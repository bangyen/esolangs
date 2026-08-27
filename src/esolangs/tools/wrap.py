r"""Wrap generated programs to a readable width, on token boundaries.

The text and boolean generators emit one long line for most languages: a
Hello-World Polynomial program is 3456 characters, which no diff or review
pane shows usefully.  Since most languages treat a newline as whitespace
(or as a comment character), such a program can be broken across lines
without changing what it does.

The wrapping is *token-aware*, and that is the whole point of this module.
Slicing a program every ``width`` characters is wrong for any language
whose tokens are longer than one character: it can split ``-6`` into ``-``
and ``6`` (a load error in the numeric languages, which is at least loud),
or split BIO's fixed-width ``0ox`` triples so that the program still runs
and prints garbage (which is not).  Each wrapper here knows what a token
is in its family and only ever breaks between two of them.

Not every language can take newlines, so wrapping is opt-in per language
rather than a blanket post-processing pass:

- The 2D languages (Dig, WII2D, and the other grid interpreters) read
  newlines as row separators, so a newline moves code to another row.
- NoComment has no comment syntax at all -- an unrecognized character is a
  load error, and that includes ``\n``.
- Forbin would tolerate a reflow -- its interpreter reads whitespace, not
  lines -- but its ``out`` statements sit one per line inside a ``main {}``
  block, and that layout is how the language is meant to be read.  Packing
  those statements to a width would cost more than the ragged right edge it
  saves, so a language whose own idiom is one-statement-per-line is left
  alone even when reflowing it would be safe.
- Basicfuck is excluded for the same reason as Forbin rather than for a
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
  source language, which is the readability the wrapping exists to serve.
  A ``//`` comment is not the obstacle it looks like either: it packs as a
  single token that forces its line to end there, which is exactly what it
  already does, and comment text too long for one line splits across
  several, each re-prefixed with ``//``.  Verified with comments injected
  into the committed example down to 30 columns.  So nothing mechanical
  stands in the way -- the exclusion is a readability judgement about
  minifying source, and only that.
- MyScript builds its output from string literals like the languages
  :data:`_QUOTE_LITERAL` covers, but its boolean program's newlines are
  structural (its blocks are indented and its interpreter reads them), so it
  cannot be wrapped by making the literal one token the way Eval is.  It is
  excluded until a wrapper that understands its block layout exists; being
  safe today only because its programs come out under one line is not the
  same as being wrappable.

ROTfuck used to belong on that list: its interpreter rotated the program on
*every* character the pointer passed, comments included, so an inserted
newline shifted every later command along the cycle.  That was a deviation
from the wiki ("every time an instruction is executed"), since a comment is
not an instruction; with it fixed, comments are transparent and ROTfuck
wraps like any other single-character-command language.

Being unwrappable is not the same as being unbounded, though.  A generator
that lays out its own *shape* can honour a width by building a different
shape, which is something no after-the-fact reflow can do: Clockwise picks
a ring that fits, Streetcode and WII2D fold their instruction line into a
boustrophedon, and LaserFuck steers the beam down and back so a straight
run of tape commands costs rows instead of columns.  Those generators take
the width themselves -- :func:`takes_width` is how the callers tell -- and
never reach :func:`wrap_program`, which would skip them anyway for being
already multi-line.

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
program under two levels deep -- every text-generator one -- is packed as
before, because indenting a flat run shows nothing.  :func:`wrap_grid`
right-aligns into columns instead: the subleq-family OISCs
(AddSubJump, Decleq, S*bleq) have uniform-width numeric tokens, so padding
each into a cell and right-aligning it lines the columns up between rows,
which is what makes a diff of one readable.  It is opt-in for the same
reason wrapping is -- Polynomial is space-delimited too, but its tokens run
from 1 to 98 characters, and padding those to a common width would be
nonsense.  Polynomial gets its own wrapper for a related reason: its
one-character tokens are the ``+`` and ``-`` between terms, and
:func:`_polynomial` glues each of those to the term it signs so that no
line is just a sign.  That wrapper then puts one term to a line rather
than packing them to the width, for the reason its docstring gives.

:data:`WRAPPERS` maps a language id to the wrapper it needs; a language
absent from it is not wrapped.  :func:`wrap_program` is the entry point the
generators and the public API call.
"""

import inspect
import re
from collections.abc import Callable

# The default width for a wrapped program.  80 is the conventional review
# and diff width, and matches the repo's own 88-column limit for Python
# closely enough that a wrapped program never looks out of place beside it.
DEFAULT_WIDTH = 80


def shortest(*candidates: str) -> str:
    """Return the shortest of ``candidates``, preferring the earlier on a tie.

    Several generators can express the same program in more than one shape --
    a ring against a fold, a minterm sum against a decision tree, an absolute
    encoding against a delta one -- and which shape wins depends on the input,
    not on the language.  Rather than predict the winner, those generators
    build every shape and emit the smallest, a rule the test suite pins in
    several places (``test_streetcode_emits_the_shorter_of_ring_and_street``,
    and the ``len(program) <= ...`` bounds in ``test_generate.py``).

    This names that rule so a reader meets it as a decision rather than
    re-deriving it from a ``min`` with a ``key``.  Ties keep the first
    argument, so callers should pass the shape they consider canonical first
    and the output stays stable when two shapes come out the same length.
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
    width and right-aligning it inside that cell makes the columns line up
    vertically, which is what makes a diff of one readable: a changed
    operand stays in its column instead of shifting every token after it.

    The cell width is :func:`_cell_width` of the program's own tokens, so
    it follows the program rather than being fixed.  A token too wide for
    one cell spans as many whole cells as it needs (see :func:`_span`)
    instead of pushing the rest of its row out of alignment -- every later
    token on the row still starts on a cell boundary.  Such a token never
    straddles a row boundary; it starts a new row if the current one
    cannot hold its span.

    Right-aligning pads on the left, so no line ever carries trailing
    whitespace.  The interpreters split on whitespace *runs*
    (:func:`~esolangs.interpreters.memory.parse_int_memory`, and S*bleq's
    own ``code.split()``), so the padding is invisible to them and the
    program means exactly what it did unpadded.
    """
    tokens = program.split()
    if not tokens:
        return program
    cell = _cell_width(tokens)
    # A row of k cells is k cells plus the k-1 single spaces between them.
    per_row = max(1, (width + 1) // (cell + 1))
    lines: list[str] = []
    row: list[str] = []
    used = 0
    for token in tokens:
        span = _span(len(token), cell)
        if row and used + span > per_row:
            lines.append(" ".join(row))
            row, used = [], 0
        # A token spanning k cells is right-aligned across the whole span:
        # its k cells plus the k-1 separators they absorb.
        row.append(token.rjust(span * cell + span - 1))
        used += span
    if row:
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


def wrap_tokens(program: str, width: int, pattern: str) -> str:
    """Wrap a program whose tokens are the matches of ``pattern``.

    Used by the languages with fixed-width multi-character commands, where
    the token boundary cannot be found by looking for whitespace.  The
    pattern must tile the program exactly -- every character belongs to some
    token -- so that rejoining the tokens reproduces the input; a program
    that does not tile is returned unwrapped rather than corrupted.
    """
    tokens = re.findall(pattern, program)
    if "".join(tokens) != program:
        return program
    return _join_tokens(tokens, width, separator="")


def wrap_chars(program: str, width: int) -> str:
    """Wrap a program whose every character is its own token.

    The single-character-command families (Brainfuck and its relatives),
    where any position is a legal break.
    """
    return "\n".join(program[i : i + width] for i in range(0, len(program), width))


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


# A BIO command is a ``[0|1][o|i][x|y|z]`` triple with the ``;`` that ends
# it, a loop-open triple carrying the ``{`` that opens its body, or the
# ``};`` that closes one -- plus the space the boolean generator separates
# commands with.  The commands are why BIO cannot be wrapped by character
# count, and their varying width is why a fixed stride will not do either.
_BIO_COMMAND = r"[01][oOiI][xXyYzZ](?:\{|;)|\};| "

# Brainfuck-family single-character commands, and the languages that
# extend them with a digit argument (Dimensional's ``>0``/``<0``).
_DIMENSIONAL_COMMAND = r"[<>]\d+|."

# The languages that print through a *literal*, where a newline dropped
# inside the literal is not whitespace between commands but a character the
# program goes on to print (or, in Sophie's case, prints *instead* of the
# one that was there).  Each pattern makes the literal a single unbreakable
# token and leaves every other character its own, so the boolean programs --
# which carry no literal -- still tokenize exactly as ``wrap_chars`` would.
#
# A literal wider than the width is then left on its own line rather than
# broken, which is :func:`_join_tokens`'s existing behaviour for an
# oversized token: a 3x hello-world is one ``[...]`` and simply does not
# wrap.  An over-wide line is the honest outcome here, since the alternative
# is a program that prints something else.
_SOPHIE_COMMAND = r"#\$\d+,|#.,?|."
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
    attaching each space to the following command makes the pair a single
    unbreakable token and keeps the newline where a space already was.

    A *nested* program is then laid out by depth rather than packed flat.
    The boolean generator nests one loop per truth-table row (``0ix{1ox
    ... }``), so its program is a telescoping chain whose shape is the
    thing worth seeing; packed to a width it reads as one undifferentiated
    run.  ``0i?`` opens a level and ``}`` closes one, so the depth is a
    running count and each line is indented by it.  The text generator's
    program is a flat sequence of depth-1 groups, where indenting would
    show nothing that packing does not, so a program shallower than two
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
    # A break after a command leaves its trailing separator at the end of the
    # line; the newline separates the commands just as well, so drop it.
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
    # Two spaces a level, up to the depth that still leaves a run a quarter
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


def _sophie(program: str, width: int) -> str:
    """Wrap Sophie, keeping each ``#<char>,`` command whole.

    Sophie prints the character *after* the ``#`` literally, so a break
    between the two makes the newline the argument: the program prints a
    newline where that character should have gone and the intended one is
    lost.  The output stays the same length, which is what makes this the
    quiet failure of the group -- ``Hello, World!`` came back as ``Hello,
    Worll!`` rather than as anything that looked wrong.
    """
    return wrap_tokens(program, width, _SOPHIE_COMMAND)


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


def _polynomial(program: str, _width: int) -> str:
    """Lay a Polynomial program out one signed term to a line.

    Polynomial's terms are space-delimited, so
    :func:`wrap_space_delimited` would wrap it -- but the ``+`` and ``-``
    between two terms are tokens of their own, and once the terms grow
    wider than the width every one of those signs lands alone on a line of
    its own.  A Hello-World program wrapped into forty lines that
    alternated a hundred-character coefficient with a single ``+``, which
    is the raggedest possible reading of a polynomial.

    Keeping each sign with the term it signs fixes that much, and packing
    the resulting pairs to a width would be the obvious next step.  This
    wrapper does not: a packed line holds however many terms happen to
    fit -- five, then two, then three -- so its breaks fall where the
    arithmetic lands rather than anywhere meaningful.  One term to a line
    makes every line the same kind of thing and the descending exponents a
    column you can read down, which is the layout a polynomial is written
    in by hand.  It is the same judgement the module docstring records for
    Forbin: a language whose own idiom is one-item-per-line is left that
    way rather than packed to a width.

    The width is therefore only the on/off switch that
    :func:`wrap_program` already applies -- the layout does not depend on
    its value, since the terms of any interesting program outrun any
    width, so the parameter is taken and ignored to keep the shape every
    :data:`WRAPPERS` entry is called with.  The header stays with the
    first term so that ``f(x)`` and ``=`` do not become lines of their
    own.

    Replacing every newline with a space reproduces the input exactly, so
    the program is untouched; the interpreter strips whitespace before
    parsing either way.
    """
    terms: list[str] = []
    pending = ""
    for token in program.split():
        if token in ("+", "-"):
            # A sign already held has no term to attach to; keep it as its
            # own line rather than dropping it.  ``format_coeffs`` never
            # emits two in a row (it collapses ``+ -`` into ``- ``), so this
            # is only about the helper staying total for any input.
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
    return "\n".join(terms)


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


def _nevermind(program: str, width: int) -> str:
    """Wrap Nevermind by re-emitting ``print,`` per line, not by breaking one.

    ``print`` writes its arguments with no separator and no trailing
    newline, so consecutive ``print`` lines concatenate: the text is split
    across as many statements as the width needs and the output is
    unchanged.  Breaking the single statement the generator emits would
    *not* work -- a newline ends it, and the remainder would be read as
    further commands, silently truncating the output.

    So the payload is cut between *units* rather than at any offset.  A
    comma in the text is encoded as ``*44``, and the interpreter expands
    that only within one argument -- split across two ``print`` lines it
    stays a literal ``*44`` and the comma is lost -- so the escape is one
    unit.  A ``$`` opening a line reads as a variable reference and halts
    the program, so it binds to the character before it.

    A unit can exceed the room a narrow width leaves, which is why the
    lines are packed rather than sliced: a width too small for a unit gets
    a line as wide as that unit needs, the same preference-not-guarantee
    the shape-building generators give it.
    """
    head, _, payload = program.partition(",")
    if head != "print" or not payload:
        return program
    room = max(width - len("print,"), 1)

    # The payload is cut between *units*, never inside one: a ``*44`` escape
    # is three characters that only expand together, and a ``$`` binds to the
    # character before it so it never opens a line.
    units: list[str] = []
    i = 0
    while i < len(payload):
        step = 3 if payload.startswith("*44", i) else 1
        # a following ``$`` would start the next line as a variable reference
        while i + step < len(payload) and payload[i + step] == "$":
            step += 1
        units.append(payload[i : i + step])
        i += step

    lines: list[str] = []
    current = ""
    for unit in units:
        if current and len(current) + len(unit) > room:
            lines.append(current)
            current = unit
        else:
            current += unit
    if current:
        lines.append(current)
    return "\n".join("print," + line for line in lines)


# Language id -> the wrapper that language needs.  A language absent here
# is never wrapped: either its newlines are semantic (the 2D grid
# languages), it rejects them outright (NoComment), or its own execution
# model makes character position meaningful (ROTfuck).  See the module
# docstring for why each exclusion is an exclusion.
WRAPPERS = {
    "addsubjump": wrap_grid,
    "decleq": wrap_grid,
    "sbleq": wrap_grid,
    # Space-delimited, but its ``+``/``-`` are tokens of their own and its
    # terms outgrow any width, so the plain space wrapper stranded every
    # sign on a line by itself; ``_polynomial`` keeps each sign with its
    # term and gives each term a line.
    "polynomial": _polynomial,
    "bitdeque": wrap_space_delimited,
    "bio": _bio,
    "dimensional": _dimensional,
    "brainfuck": wrap_chars,
    "three_d_brainfuck": wrap_chars,
    "circlefuck": wrap_chars,
    "minifuck": wrap_chars,
    "factor": wrap_chars,
    "home_row": wrap_chars,
    "painfuck": wrap_chars,
    "bit_tilde": wrap_chars,
    "six_five": wrap_chars,
    "unsquare": wrap_chars,
    "pct_squared_minus_one": wrap_chars,
    "rotfuck": wrap_chars,
    "bfstack": wrap_chars,
    "suffolk": wrap_chars,
    # 123 is single-character commands throughout -- its trailing ``1`` is a
    # terminator, not a structural line -- so any position is a legal break.
    "one_two_three": wrap_chars,
    # SLOW ACV MAMMALIAN's commands are whole words (``SEED``, ``SPRINT``,
    # ``DIGEST``), so it wraps on whitespace like the numeric languages;
    # breaking by character count would split a word and change the program.
    "slow_acv_mammalian": wrap_space_delimited,
    # Their boolean programs are single long lines that need wrapping, and
    # their text programs print through a literal that must not be broken;
    # the literal-aware wrappers above cover both dialects at once.
    "modulous": _bracket_literal,
    "eval": _quote_literal,
    "sophie": _sophie,
    "three_x": _bracket_literal,
    # Forth's commands are single characters throughout, with no literal.
    "forth": wrap_chars,
    # Both concatenate their command text before reading it, so a line break
    # can never land inside a command: Taglate joins every line after the
    # queue seed and only then tokenizes (so a two-character ``gy``/``gz``
    # cannot be split across rows), and A Painter Ant drops whitespace
    # outright.  Their hello-world programs are short; the boolean ones are
    # the single long lines that need this.
    "taglate": _taglate,
    # Line-based: a newline ends a statement rather than continuing it, so
    # this re-emits ``print,`` per line instead of breaking the one the
    # generator produces.  See :func:`_nevermind`.
    "nevermind": _nevermind,
    "a_painter_ant": wrap_chars,
}


# The languages whose wrapper handles an already-multi-line program itself,
# rather than being skipped by :func:`wrap_program` for having a newline in
# it.  Taglate's first line seeds its queue and is structural; every other
# wrapped language arrives as a single line.
MULTILINE = frozenset({"taglate"})


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
