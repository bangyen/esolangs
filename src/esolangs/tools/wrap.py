"""Wrap generated programs to a readable width, on token boundaries.

Most generators emit one long line and most languages read a newline as
whitespace.  Wrapping is token-aware (slicing every ``width`` splits
``-6`` or BIO's ``0ox`` triples) and opt-in: 2D languages read newlines as
rows, NoComment rejects them, Forbin and Packlang fold only an over-wide
line.

Ten generators lay out their own shape instead (:func:`takes_width`):
Streetcode and LaserFuck fold into a boustrophedon; Clockwise and
Flowchart stack a column per node; Dig turns
once; Alight and Super SNUSP steer; function x(y) and APL name a
subexpression per line; Circuit Diagram bands.  Only Clockwise folds to
any width; the rest floor (Flowchart ``n + 5``, Alight ``2 ** n``, Super SNUSP
four, Circuit Diagram ~``10 * n``) and return the narrowest program.

:data:`MULTILINE` names the wrappers that handle their own structural
lines.  :func:`_bio` indents by loop depth, :func:`wrap_grid` right-aligns
the subleq OISCs into cells, Polynomial glues each sign to its term.
:data:`WRAPPERS` maps a language id to its wrapper; :func:`wrap_program`
is the entry point.
"""

import inspect
import re
from collections.abc import Callable

from esolangs.tools.helpers import MARK, MOST_INPUTS, mark

# 80: the conventional review/diff width, close to the repo's 88 for Python.
DEFAULT_WIDTH = 80


def shortest(*candidates: str) -> str:
    """Return the shortest of ``candidates``, preferring the earlier on a tie.

    Several generators build every shape (ring vs fold, minterm sum vs tree)
    and emit the smallest; ties keep the first, so pass the canonical shape
    first for stable output.
    """
    return min(candidates, key=len)


def wrap_space_delimited(program: str, width: int) -> str:
    """Wrap a whitespace-delimited program, never splitting a token.

    A token longer than ``width`` gets its own line.
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

    Cells of :func:`_cell_width` line the subleq OISCs' columns up so a
    changed operand stays in its column; a wide token spans whole cells
    (:func:`_span`) and never straddles a row.  Left padding only, and the
    interpreters split on whitespace runs.
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

    ``SEED`` forms nearly every long run; the other words span two or three cells.
    """
    tokens = program.split()
    if not tokens:
        return program
    return _wrap_grid(tokens, width, 4, left_aligned=True)


def _cell_width(tokens: list[str]) -> int:
    """Return the cell width the bulk of ``tokens`` fits in.

    An outlier at least twice the next distinct width is dropped and spans
    cells instead, so a few long literals do not pad the whole file.
    """
    widths = sorted({len(token) for token in tokens}, reverse=True)
    while len(widths) > 1 and widths[0] >= 2 * widths[1]:
        widths.pop(0)
    return widths[0]


def _span(length: int, cell: int) -> int:
    """Return how many whole cells a token of ``length`` characters needs.

    ``k`` cells hold ``k * cell + (k - 1)`` characters.
    """
    return max(1, -(-(length + 1) // (cell + 1)))


#: One input's mark run (:func:`~esolangs.tools.helpers.mark`), one token:
#: a break inside would land inside the setter.  Adjacent runs are two tokens.
_RUN = "|".join(f"{re.escape(mark(i))}+" for i in range(MOST_INPUTS))


def wrap_tokens(program: str, width: int, pattern: str) -> str:
    """Wrap a program whose tokens are the matches of ``pattern``.

    ``pattern`` must tile the program exactly; one that does not is returned
    unwrapped.  A :data:`_RUN` is tried ahead of ``pattern``.
    """
    tokens = re.findall(f"{_RUN}|{pattern}", program)
    if "".join(tokens) != program:
        return program
    return _join_tokens(tokens, width, separator="")


def wrap_chars(program: str, width: int) -> str:
    """Wrap a program whose every character is its own token.

    Any position is a legal break, except inside a template's :data:`_RUN`.
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

# Literal-printing languages: the literal is one token (an over-wide one
# gets its own line).  Sophie: numeric load and branch, then the
# one-character forms, longest first (``#\$\d+,`` with the comma required
# once tokenized ``#$1`` as ``#$`` + ``1``); ``}{`` is an if-close beside
# an else-open, and a newline between loses the else.
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

    The separating space attaches to the following command.  ``0i?`` opens a
    level and ``}`` closes, so a program two or more levels deep is indented
    by depth (the boolean generator nests one loop per row).
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
    """Whether ``token`` opens a BIO loop: the ``0i?`` triple *with* its ``{``."""
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

    The run between an open and a close (the ``0oy`` ramp) packs to the
    remaining width; the indent stops growing once a run would have less
    than a quarter of the width.
    """
    lines: list[str] = []
    depth = 0
    run: list[str] = []
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

    ``7``/``8`` take the next character as operand (``num("\n")`` is -45),
    and ``7n`` skips the next *token*, a newline included: ``706A`` leaves
    cell 0, ``70\n6A`` cell 6.  So ``7n`` plus what follows is one token;
    ``8n`` counts ``4`` markers and needs no pairing.
    """
    return wrap_tokens(program, width, _SIX_FIVE_COMMAND)


def _sophie(program: str, width: int) -> str:
    """Wrap Sophie, keeping each ``#<char>,`` command whole.

    A newline after ``#`` is printed in place of the character, same length:
    ``Hello, World!`` came back ``Hello, Worll!``.
    """
    return wrap_tokens(program, width, _SOPHIE_COMMAND)


def _minifuck(program: str, width: int) -> str:
    """Wrap Minifuck, keeping a ``[`` run with the character it may skip.

    ``[`` skips two *characters*, a newline included; a run chains, so in
    ``[[x`` a break before ``x`` is unsafe.
    """
    return wrap_tokens(program, width, _MINIFUCK_COMMAND)


def _bitdeque(program: str, width: int) -> str:
    r"""Wrap Bitdeque, keeping each ``GOTO`` with the operand it jumps to.

    The parser spells ``GOTO *(\d+)`` with spaces, not whitespace, so a break
    there silently answers 1 for 0 -- at widths 12 and 13 only.
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

    ``3?`` and ``12+`` put the operand first; a bare ``?`` is a load error,
    and the failure is positional (10, 17, 25, 37, 50 fail; 40 and 80 pass).
    """
    return wrap_tokens(program, width, _JAUNE_COMMAND)


def _bracket_literal(program: str, width: int) -> str:
    """Wrap 3x and Modulous, keeping a bracketed group whole.

    Both print through a bracketed literal, so a newline inside it prints.
    """
    return wrap_tokens(program, width, _BRACKET_LITERAL)


def _quote_literal(program: str, width: int) -> str:
    """Wrap Eval, keeping literals and conditional commands whole."""
    return wrap_tokens(program, width, _EVAL_UNIT)


def _polynomial(program: str, width: int) -> str:
    """Lay a Polynomial program out one signed term to a line.

    The space wrapper stranded every sign alone between wide terms.  One
    term to a line, not packed, so the exponents read as a column; the term
    itself folds too (a coefficient is 5950 digits on the dense eight-input
    table).  Folding inside a number is safe: ``_parse_program`` deletes
    every non-digit non-operator character before parsing, and ``sanitize``
    sizes its digit cap from the cleaned text (checked on that table).
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

    Not indented: that would be invented whitespace, and the suite's
    invariant is that deleting what the wrapper inserted gives the program back.
    """
    rows = [term[i : i + width] for i in range(0, len(term), max(1, width))]
    return "\n".join(rows)


def _taglate(program: str, width: int) -> str:
    """Wrap Taglate's commands, leaving its queue-seed line alone.

    The first line seeds the queue and is structural; the rest is joined
    before tokenizing and breaks anywhere.
    """
    seed, _, commands = program.partition("\n")
    if not commands:
        return program
    return seed + "\n" + wrap_chars(commands.replace("\n", ""), width)


def _qoibl(program: str, width: int) -> str:
    """Wrap Qoibl, folding each of its lines but keeping them apart.

    A newline between tokens is whitespace (measured), so each statement
    line folds on its own; joining first would fold across statements.
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
    "bf_pda": wrap_chars,
    # One statement a line; each folds on its own.
    "qoibl": _qoibl,
    # Generators emit indented blocks; fold only an over-wide line.
    "forbin": _indented,
    "packlang": _indented,
}


# Wrappers that handle a multi-line program themselves instead of being
# skipped: Taglate's first line seeds its queue (kept whole); Qoibl's every
# line is a statement, folded separately for the reader (the language would
# not notice).
MULTILINE = frozenset({"taglate", "qoibl", "forbin", "packlang"})


def takes_width(fn: Callable[..., str]) -> bool:
    """Whether a generator lays its own program out to a width.

    Such a generator takes ``width`` directly; :func:`wrap_program` cannot
    help a grid, since it leaves a multi-line program alone.
    """
    try:
        return "width" in inspect.signature(fn).parameters
    except (TypeError, ValueError):  # pragma: no cover - builtins have no signature
        return False


def wrap_program(program: str, language_id: str, width: int | None) -> str:
    """Return ``program`` wrapped to ``width`` columns, if that is possible.

    ``None`` means do not wrap (the default).  A language that cannot take
    newlines, and a program already multi-line, are returned unchanged
    rather than raising; a :data:`MULTILINE` wrapper knows which lines are structural.
    """
    if width is None or width <= 0:
        return program
    if "\n" in program and language_id not in MULTILINE:
        return program
    wrapper = WRAPPERS.get(language_id)
    if wrapper is None:
        return program
    return wrapper(program, width)
