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

Most wrappers only decide *where* the newlines go.  :func:`wrap_grid` also
decides where the tokens sit within a line: the subleq-family OISCs
(AddSubJump, Decleq, S*bleq) have uniform-width numeric tokens, so padding
each into a cell and right-aligning it lines the columns up between rows,
which is what makes a diff of one readable.  It is opt-in for the same
reason wrapping is -- Polynomial is space-delimited too, but its tokens run
from 1 to 98 characters, and padding those to a common width would be
nonsense.

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

    The widest token is not always the right cell width: Decleq's boolean
    program is 321 tokens of three characters or fewer alongside four
    ten-character jump sentinels, and sizing every cell to the sentinel
    would pad the whole file out to seven sparse columns.  So an outlier is
    dropped while it is at least twice the next distinct width, and the
    tokens that remain set the width; the dropped ones span several cells
    instead.
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


# A BIO command is a ``[0|1][o|i][x|y|z]`` triple, a loop brace, or the
# space the boolean generator separates commands with.  The triples are why
# BIO cannot be wrapped by character count, and the braces are why it
# cannot be wrapped by a fixed stride of three either.
_BIO_COMMAND = r"[01][oOiI][xXyYzZ]|[{}]| "

# Brainfuck-family single-character commands, and the languages that
# extend them with a digit argument (Dimensional's ``>0``/``<0``).
_DIMENSIONAL_COMMAND = r"[<>]\d+|."


def _bio(program: str, width: int) -> str:
    # The boolean BIO generator separates commands with spaces while the text
    # one does not, so a space is one of BIO's tokens here.  A line must not
    # start with that separator, so break *before* the command it precedes:
    # attaching each space to the following command makes the pair a single
    # unbreakable token and keeps the newline where a space already was.
    tokens = re.findall(_BIO_COMMAND, program)
    if "".join(tokens) != program:
        return program
    merged: list[str] = []
    for token in tokens:
        if token.isspace() and merged:
            merged[-1] += token
        else:
            merged.append(token)
    wrapped = _join_tokens(merged, width, separator="")
    # A break after a command leaves its trailing separator at the end of the
    # line; the newline separates the commands just as well, so drop it.
    return "\n".join(line.rstrip(" ") for line in wrapped.split("\n"))


def _dimensional(program: str, width: int) -> str:
    return wrap_tokens(program, width, _DIMENSIONAL_COMMAND)


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


# Language id -> the wrapper that language needs.  A language absent here
# is never wrapped: either its newlines are semantic (the 2D grid
# languages), it rejects them outright (NoComment), or its own execution
# model makes character position meaningful (ROTfuck).  See the module
# docstring for why each exclusion is an exclusion.
WRAPPERS = {
    "addsubjump": wrap_grid,
    "decleq": wrap_grid,
    "sbleq": wrap_grid,
    "polynomial": wrap_space_delimited,
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
    # Their hello-world programs already come out multi-line and short, but
    # their *boolean* programs are single long lines, so both still need a
    # wrapper.
    "bfstack": wrap_chars,
    "suffolk": wrap_chars,
    "modulous": wrap_chars,
    "forth": wrap_chars,
    "eval": wrap_chars,
    "sophie": wrap_chars,
    "myscript": wrap_chars,
    "three_x": wrap_chars,
    # Both concatenate their command text before reading it, so a line break
    # can never land inside a command: Taglate joins every line after the
    # queue seed and only then tokenizes (so a two-character ``gy``/``gz``
    # cannot be split across rows), and A Painter Ant drops whitespace
    # outright.  Their hello-world programs are short; the boolean ones are
    # the single long lines that need this.
    "taglate": _taglate,
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
