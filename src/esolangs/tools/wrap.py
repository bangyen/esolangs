"""Wrap generated programs to a readable width, on token boundaries.

Most generators emit one long line and most languages read a newline as
whitespace.  Wrapping is token-aware (slicing every ``width`` splits
``-6`` or BIO's ``0ox`` triples) and opt-in: 2D languages read newlines as
rows; Packlang folds only an over-wide line.

Generators detected by :func:`takes_width` lay out their own programs.
They preserve structural lines and return a width floor when the requested
width cannot fit whole tokens, statements or routing cells.

:data:`MULTILINE` names the wrappers that handle their own structural
lines.  :func:`_bio` indents by loop depth, :func:`wrap_grid` right-aligns
the subleq OISCs into cells, Polynomial glues each sign to its term.
:data:`WRAPPERS` maps a language id to its wrapper; :func:`wrap_program`
is the entry point.
"""

import inspect
import re
from collections.abc import Callable
from itertools import pairwise
from math import isqrt

from esolangs.tools.helpers import MARK, MOST_INPUTS, mark
from esolangs.tools.token_balance import balanced_token_width

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


_PACKLANG_LEXEME = r"[A-Za-z_][A-Za-z_0-9]*|\d+|[{}();:,^!]"


def _packlang(program: str, width: int) -> str:
    """Fold complete Packlang lexical tokens, reducing indent when necessary."""
    lines = []
    for line in program.split("\n"):
        if len(line) <= width:
            lines.append(line)
            continue
        tokens = re.findall(_PACKLANG_LEXEME, line)
        if "".join(tokens) != "".join(line.split()):
            return program
        indent = line[: len(line) - len(line.lstrip())]
        indent = indent[: max(0, width - max(map(len, tokens), default=0))]
        folded = _join_tokens(tokens, max(1, width - len(indent)), separator=" ")
        lines.extend(indent + part for part in folded.split("\n"))
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
    cells, remainder = divmod(length + 1, cell + 1)
    if remainder:
        cells += 1
    return max(1, cells)


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

# Dimensional's operands, all of which a break would split.  ``_number``
# takes an optional ``~`` and a digit run for ``<``, ``>``, ``$``, ``{``,
# ``?`` and ``!``; ``=`` takes exactly two hex digits and ``:`` exactly one
# character, newline included.  Binding a pair the interpreter would not
# have read -- a ``:`` inside a ``*`` comment -- only costs a break.
_DIMENSIONAL_COMMAND = r"[<>$?!{]~?\d*|=[\s\S]{0,2}|:[\s\S]?|[\s\S]"

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
# stays with the character after it, or with the input run after it.
_MINIFUCK_COMMAND = rf"\[+(?:{_RUN}|[\s\S])|[\s\S]"

# Jaune: operand before operator (``3?``, ``2+``, ``v?``) is the only
# unbreakable unit. Splitting ``++4:`` makes its final plus a label sign.
_JAUNE_COMMAND = r"[+-]{2,}|[+-]?\d+[-+:?!$@]|v[-+?!@:$]|."
_BRACKET_LITERAL = r"\[[^\]]*\]|."
_EVAL_UNIT = r'"[^"]*"|\?.|.'

# FALSE ``'`` pushes the *next* character, so ``'0`` is one token and a
# newline between the two pushes 10 instead of 48.  A ``{comment}`` or
# ``"string"`` would be a third unit; no generated program has either.
_FALSE_COMMAND = r"'[\s\S]|[\s\S]"

# Unlambda ``.x`` and ``?x`` take the next character too: a break inside
# ``.0`` prints a newline, and one inside ``?0`` asks about one.
_UNLAMBDA_COMMAND = r"[.?][\s\S]|[\s\S]"


def _bio(program: str, width: int) -> str:
    """Wrap BIO, indenting a nested program by its loop depth.

    The separating space attaches to the following command.  ``0i?`` opens a
    level and ``}`` closes, so a program two or more levels deep is indented
    by depth (the boolean generator nests one loop per row).
    """
    merged = _bio_tokens(program)
    if merged is None:
        return program
    if _bio_depth(merged) >= 2:
        return _bio_indented(merged, width)
    wrapped = _join_tokens(merged, width, separator="")
    # The newline replaces the trailing separator.
    return "\n".join(line.rstrip(" ") for line in wrapped.split("\n"))


def _bio_tokens(program: str) -> list[str] | None:
    """Return BIO commands with their trailing separators, if they tile source."""
    tokens = re.findall(f"{_RUN}|{_BIO_COMMAND}", program)
    if "".join(tokens) != program:
        return None
    merged: list[str] = []
    for token in tokens:
        if token.isspace() and merged:
            merged[-1] += token
        else:
            merged.append(token)
    return merged


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
    cap = max(0, (width - width // 4) // 2)
    for depth, run in _bio_runs(tokens):
        pad = " " * (2 * min(depth, cap))
        room = max(width - len(pad), width // 4)
        for line in _join_tokens(run, room, separator="").split("\n"):
            lines.append((pad + line).rstrip(" "))
    return "\n".join(lines)


def _bio_runs(tokens: list[str]) -> list[tuple[int, list[str]]]:
    """Return structural straight runs with their loop depth."""
    groups: list[tuple[int, list[str]]] = []
    depth = 0
    run: list[str] = []

    def flush(at: int) -> None:
        """Retain a nonempty run without sharing its mutable buffer."""
        if run:
            groups.append((at, run.copy()))
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
    return groups


def _balance_bio(program: str) -> str:
    """Balance shallow token fits or nested padding-cap and run-fit regimes."""
    tokens = _bio_tokens(program)
    if tokens is None:
        return program
    if _bio_depth(tokens) < 2:
        width = balanced_token_width(tokens, rstrip_rows=True)
        return min(program, _bio(program, width), key=balance_score)
    groups = _bio_runs(tokens)
    full_spans = [2 * depth + len("".join(run).rstrip(" ")) for depth, run in groups]
    widest = max(full_spans)
    if widest <= len(groups):
        # Every layout has at least one row per structural run and no row
        # wider than its fully indented run. Attaining both bounds is optimal.
        target = min(
            depth
            for (depth, _run), span in zip(groups, full_spans, strict=True)
            if span == widest
        )
        cap_widths = []
        for residue in range(8):
            fixed = (residue - residue // 4) // 2
            remainder = residue - 2 * fixed
            quotient = max(0, -((residue - 1) // 8), -((fixed - target) // 3))
            for depth, run in groups:
                if len(run) > 1:
                    length = sum(map(len, run))
                    # For w=8q+r, room=max(2q+r-2f, 8q+r-2depth).
                    quotient = max(
                        quotient,
                        min(
                            -((remainder - length) // 2),
                            -((residue - 2 * depth - length) // 8),
                        ),
                    )
            cap_widths.append(8 * quotient + residue)
        width = min(cap_widths, key=lambda value: ((value - value // 4) // 2, value))
        return min(program, _bio_indented(tokens, width), key=balance_score)

    depth_limit = max(depth for depth, _run in groups)
    fits: list[tuple[int, set[int]]] = []
    for depth, run in groups:
        lengths = list(map(len, run))
        if len(set(lengths)) == 1:
            spans = set(range(lengths[0], sum(lengths) + 1, lengths[0]))
        else:
            prefix = [0]
            for length in lengths:
                prefix.append(prefix[-1] + length)
            spans = {
                end - start
                for at, start in enumerate(prefix[:-1])
                for end in prefix[at + 1 :]
            }
        fits.append((depth, spans))
    widths = set()
    for cap in range(depth_limit + 1):
        lower = max(1, 2 * cap + 2 * cap // 3)
        stop = (
            2 * (cap + 1) + 2 * (cap + 1) // 3 - 1
            if cap < depth_limit
            else max(lower, max(2 * depth + max(spans) for depth, spans in fits))
        )
        widths.add(lower)
        for depth, spans in fits:
            pad = 2 * min(depth, cap)
            widths.update(pad + span for span in spans if lower < pad + span <= stop)
    # Padding is fixed within each cap interval; only whole run fits can
    # change its source. Beyond the last fit, the layout is constant.
    candidates = [_bio_indented(tokens, width) for width in sorted(widths)]
    return min(program, *candidates, key=balance_score)


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
    tokens = re.findall(f"{_RUN}|{_MINIFUCK_COMMAND}", program)
    floor = max(map(len, tokens), default=0)
    if "\n" in program and max(map(len, program.split("\n"))) <= max(width, floor):
        return program
    return _join_tokens(tokens, width, separator="")


def _false(program: str, width: int) -> str:
    """Wrap FALSE, keeping each ``'x`` character push whole."""
    return wrap_tokens(program, width, _FALSE_COMMAND)


def _unlambda(program: str, width: int) -> str:
    """Wrap Unlambda, keeping each ``.x`` print and ``?x`` test whole."""
    return wrap_tokens(program, width, _UNLAMBDA_COMMAND)


def _bitdeque(program: str, width: int) -> str:
    """Wrap Bitdeque, keeping each ``GOTO`` with its target operand."""
    return _join_tokens(_bitdeque_tokens(program), width, separator=" ")


def _bitdeque_tokens(program: str) -> list[str]:
    """Return Bitdeque commands with their attached branch operands."""
    tokens: list[str] = []
    for token in program.split():
        if tokens and tokens[-1] == "GOTO":
            tokens[-1] = f"GOTO {token}"
        else:
            tokens.append(token)
    return tokens


def _jaune(program: str, width: int) -> str:
    """Wrap Jaune, keeping each operand attached to the operator it feeds.

    ``3?`` and ``12+`` put the operand first; a bare ``?`` is a load error,
    and the failure is positional (10, 17, 25, 37, 50 fail; 40 and 80 pass).
    """
    return wrap_tokens(program, width, _JAUNE_COMMAND)


def _bracket_literal(program: str, width: int) -> str:
    """Wrap 3x, keeping a bracketed group whole.

    A newline inside its bracketed literal prints.
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
    return "\n".join(_folded_term(term, width) for term in _polynomial_terms(program))


def _polynomial_terms(program: str) -> list[str]:
    """Return signed terms, retaining the leading function declaration."""
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
    return terms


def _balance_polynomial(program: str) -> str:
    """Balance term folds at their integer-division transitions."""
    terms = _polynomial_terms(program)
    if not terms:
        return program
    lengths = list(map(len, terms))
    total = sum(lengths)
    widest = max(lengths)
    events = {1: 0, widest + 1: 0}
    for length in lengths:
        remainder = length - 1
        # ceil(length/w) = 1+floor(remainder/w). Its distinct quotient
        # endpoints are divisor pairs through sqrt(remainder).
        for divisor in range(1, isqrt(remainder) + 1):
            for boundary in {divisor + 1, remainder // divisor + 1}:
                change = remainder // boundary - remainder // (boundary - 1)
                events[boundary] = events.get(boundary, 0) + change
    height = total
    choices: list[tuple[tuple[int, int, int], int]] = []
    for lower, stop in pairwise(sorted(events)):
        height += events[lower]
        width = min(stop - 1, max(lower, height))
        choices.append(((abs(width - height), total + height - 1, width), width))
    _, width = min(choices)
    return min(program, _polynomial(program, width), key=balance_score)


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


# Language id -> wrapper; semantic newlines require generator-owned layouts.
WRAPPERS = {
    "addsubjump": wrap_grid,
    "decleq": wrap_grid,
    "sbleq": wrap_grid,
    "subleq": wrap_grid,
    "boolfuck": wrap_chars,
    "cyclic_tag": wrap_chars,
    # Space wrap stranded every sign alone; keep sign with term, one per line.
    "polynomial": _polynomial,
    # Space-delimited, but ``GOTO`` and its target must stay on one line.
    "bitdeque": _bitdeque,
    "bio": _bio,
    "dimensional": _dimensional,
    # 7n/8n are two-character tokens; see :func:`_six_five`.
    "six_five": _six_five,
    # Safe anywhere: every space and newline is stripped before parsing.
    "bitwise_cyclic_tag": wrap_chars,
    # Loader whitespace is discarded before assigning memory addresses.
    "malbolge": wrap_chars,
    # LF-only source-format deviation: discard breaks before parsing or addressing.
    "cvnc": wrap_chars,
    "grapheme": wrap_chars,
    "nocomment": wrap_chars,
    "brainfuck": wrap_chars,
    "circlefuck": wrap_chars,
    # ``[`` skips the character after it.
    "minifuck": _minifuck,
    "factor": wrap_chars,
    "home_row": wrap_chars,
    "painfuck": wrap_chars,
    "bit_tilde": wrap_chars,
    "unsquare": wrap_chars,
    "rotfuck": wrap_chars,
    "smallfuck": wrap_chars,
    "bfstack": wrap_chars,
    # Whitespace is discarded anywhere, inside a token too.
    "sstack": wrap_chars,
    "suffolk": wrap_chars,
    # The trailing ``1`` is a terminator, not a structural line.
    "one_two_three": wrap_chars,
    # Four-character cells align the ``SEED`` runs; longer words span cells.
    "slow_acv_mammalian": _mammalian,
    # Multi-character tokens (``vs``, ``0b1``, ``L C 19``); space is the
    # only safe break.
    "ram0": wrap_space_delimited,
    # Operand-before-operator, so a break between the two is a load error.
    "jaune": _jaune,
    # Print through a literal that must not be broken.
    "eval": _quote_literal,
    # ``'x`` and ``.x``/``?x`` take the character after them.
    "false": _false,
    "unlambda": _unlambda,
    # Whitespace- or comma-separated tokens, and a break inside one would
    # change a number.
    "fractran": wrap_space_delimited,
    "sophie": _sophie,
    "three_x": _bracket_literal,
    "forth": wrap_chars,
    # Both concatenate before tokenizing (Taglate after the queue seed; A
    # Painter Ant drops whitespace), so no break can land inside a command.
    "taglate": _taglate,
    "a_painter_ant": wrap_chars,
    "bf_pda": wrap_chars,
    # One statement a line; each folds on its own.
    # Generators emit indented blocks; fold only an over-wide line.
    # Packlang punctuation separates tokens even without a space.
    "packlang": _packlang,
}


# These wrappers preserve structural rows or existing newline comments.
MULTILINE = frozenset(
    language_id
    for language_id, wrapper in WRAPPERS.items()
    if wrapper in {_taglate, _packlang, _minifuck}
)


def takes_width(fn: Callable[..., object]) -> bool:
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


def balance_width(program: str) -> int:
    """Return a square target width from the default rendered area."""
    rows = program.split("\n")
    area = max(1, sum(map(len, rows)))
    return isqrt(area - 1) + 1


def balance_program(program: str, language_id: str) -> str:
    """Balance whole-token fits and term folds; otherwise estimate source area."""
    wrapper = WRAPPERS.get(language_id)
    if "\n" not in program and wrapper is _polynomial:
        return _balance_polynomial(program)
    if "\n" not in program and wrapper is _bio:
        return _balance_bio(program)
    if "\n" not in program and wrapper is wrap_space_delimited:
        tokens = program.split()
        width = balanced_token_width(tokens, " ")
        return min(program, _join_tokens(tokens, width, " "), key=balance_score)
    patterns = {
        "dimensional": _DIMENSIONAL_COMMAND,
        "six_five": _SIX_FIVE_COMMAND,
        "jaune": _JAUNE_COMMAND,
        "false": _FALSE_COMMAND,
        "unlambda": _UNLAMBDA_COMMAND,
        "sophie": _SOPHIE_COMMAND,
        "three_x": _BRACKET_LITERAL,
        "eval": _EVAL_UNIT,
    }
    pattern = patterns.get(language_id)
    if "\n" not in program and pattern is not None:
        tokens = re.findall(f"{_RUN}|{pattern}", program)
        width = balanced_token_width(tokens)
        return min(program, _join_tokens(tokens, width, ""), key=balance_score)
    if (
        wrapper is wrap_chars
        and any(MARK <= ord(c) < MARK + MOST_INPUTS for c in program)
        and "\n" not in program
    ):
        tokens = re.findall(f"{_RUN}|[\\s\\S]", program)
        width = balanced_token_width(tokens)
        return min(program, _join_tokens(tokens, width, ""), key=balance_score)
    if "\n" not in program and wrapper in (wrap_grid, _mammalian):
        tokens = program.split()
        if not tokens:
            return program
        cell = 4 if wrapper is _mammalian else _cell_width(tokens)
        aligned = [
            token.ljust(_span(len(token), cell) * (cell + 1) - 1)
            if wrapper is _mammalian
            else token.rjust(_span(len(token), cell) * (cell + 1) - 1)
            for token in tokens
        ]
        width = balanced_token_width(aligned, " ", rstrip_rows=True)
        return min(
            program, wrap_program(program, language_id, width), key=balance_score
        )
    candidate = wrap_program(program, language_id, balance_width(program))
    return min((program, candidate), key=balance_score)


def balance_score(program: str) -> tuple[int, int, int]:
    """Rank rendered shapes by imbalance, length, then width."""
    rows = program.split("\n")
    width = max(map(len, rows), default=0)
    return abs(width - len(rows)), len(program), width
