"""Wrap generated programs to a readable width, on token boundaries.

Most generators emit one long line and most languages read a newline as
whitespace. Wrapping is token-aware: slicing every ``width`` can split a
command. It is opt-in because 2D languages read newlines as rows.

Generators detected by :func:`takes_width` lay out their own programs.
They preserve structural lines and return a width floor when the requested
width cannot fit whole tokens, statements or routing cells.

:data:`MULTILINE` names the wrappers that handle their own structural
lines. Language-owned wrappers preserve their own token and term boundaries;
:func:`wrap_grid` right-aligns instruction cells.
:data:`WRAPPERS` maps a language id to the wrapper its ``LANGUAGE`` names
(``wrap=``); :func:`wrap_program` is the entry point.
"""

import inspect
import re
from collections.abc import Callable
from math import isqrt
from typing import Any

from esolangs.generation.helpers import MARK, MOST_INPUTS, mark
from esolangs.generation.token_balance import balanced_token_width

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
    padding = {}
    for token in set(tokens):
        span = _span(len(token), cell)
        slot = span * (cell + 1) - 1
        padding[token] = (
            span,
            token.ljust(slot) if left_aligned else token.rjust(slot),
        )
    for token in tokens:
        span, padded = padding[token]
        if row and used + span > per_row:
            lines.append(" ".join(row).rstrip())
            row, used = [], 0
        row.append(padded)
        used += span
    # ``row`` always holds the last row here (empty ``tokens`` returned above).
    if row:  # pragma: no branch - never empty; see above
        lines.append(" ".join(row).rstrip())
    return "\n".join(lines)


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


#: One input's mark run (:func:`~esolangs.generation.helpers.mark`), one token:
#: a break inside would land inside the setter.  Adjacent runs are two tokens.
_RUN = "|".join(f"{re.escape(mark(i))}+" for i in range(MOST_INPUTS))
_MARK_PATTERN = re.compile(f"[{chr(MARK)}-{chr(MARK + MOST_INPUTS - 1)}]")


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
    if not _MARK_PATTERN.search(program):
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


def _jaune(program: str, width: int) -> str:
    """Wrap Jaune, keeping each operand attached to the operator it feeds.

    ``3?`` and ``12+`` put the operand first; a bare ``?`` is a load error,
    and the failure is positional (10, 17, 25, 37, 50 fail; 40 and 80 pass).
    """
    return wrap_tokens(program, width, _JAUNE_COMMAND)


def _bracket_literal(program: str, width: int) -> str:
    """Wrap bracket literals, keeping a bracketed group whole.

    A newline inside its bracketed literal prints.
    """
    return wrap_tokens(program, width, _BRACKET_LITERAL)


def _quote_literal(program: str, width: int) -> str:
    """Wrap Eval, keeping literals and conditional commands whole."""
    return wrap_tokens(program, width, _EVAL_UNIT)


def __getattr__(name: str) -> Any:
    """Derive ``WRAPPERS`` and ``MULTILINE`` from the registry on first use.

    Each language names its wrapper in its own ``LANGUAGE`` (``wrap=``); the
    registry imports the generators, which import this module, so the
    tables cannot be built while it loads.
    """
    if name not in {"WRAPPERS", "MULTILINE"}:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from esolangs.registry import LANGUAGES

    wrappers = {lang.id: lang.wrap for lang in LANGUAGES.values() if lang.wrap}
    globals()["WRAPPERS"] = wrappers
    globals()["MULTILINE"] = frozenset(
        lang.id for lang in LANGUAGES.values() if lang.wrap and lang.wrap_multiline
    )
    return globals()[name]


def _wrapper(language_id: str) -> Callable[[str, int], str] | None:
    """Return the wrapper the language with ``language_id`` declares."""
    from esolangs.registry import LANGUAGES

    return next(
        (lang.wrap for lang in LANGUAGES.values() if lang.id == language_id), None
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
    wrapper = _wrapper(language_id)
    if "\n" in program:
        from esolangs.registry import LANGUAGES

        if not any(
            lang.id == language_id and lang.wrap_multiline
            for lang in LANGUAGES.values()
        ):
            return program
    if wrapper is None:
        return program
    return wrapper(program, width)


def balance_width(program: str) -> int:
    """Return a square target width from the default rendered area."""
    rows = program.split("\n")
    area = max(1, sum(map(len, rows)))
    return isqrt(area - 1) + 1


def _token_patterns() -> dict[Callable[[str, int], str], str]:
    """Each token wrapper's token: it balances over what it breaks between."""
    return {
        _dimensional: _DIMENSIONAL_COMMAND,
        _six_five: _SIX_FIVE_COMMAND,
        _jaune: _JAUNE_COMMAND,
        _false: _FALSE_COMMAND,
        _unlambda: _UNLAMBDA_COMMAND,
        _sophie: _SOPHIE_COMMAND,
        _bracket_literal: _BRACKET_LITERAL,
        _quote_literal: _EVAL_UNIT,
    }


def balance_program(program: str, language_id: str) -> str:
    """Balance whole-token fits and term folds; otherwise estimate source area."""
    from esolangs.registry import LANGUAGES

    source_balance = next(
        (lang.wrap_balance for lang in LANGUAGES.values() if lang.id == language_id),
        None,
    )
    if "\n" not in program and source_balance is not None:
        return source_balance(program)
    wrapper = _wrapper(language_id)
    if "\n" not in program and wrapper is wrap_space_delimited:
        tokens = program.split()
        width = balanced_token_width(tokens, " ")
        return min(program, _join_tokens(tokens, width, " "), key=balance_score)
    pattern = _TOKEN_PATTERNS.get(wrapper) if wrapper is not None else None
    if "\n" not in program and pattern is not None:
        tokens = re.findall(f"{_RUN}|{pattern}", program)
        width = balanced_token_width(tokens)
        return min(program, _join_tokens(tokens, width, ""), key=balance_score)
    if wrapper is wrap_chars and _MARK_PATTERN.search(program) and "\n" not in program:
        tokens = re.findall(f"{_RUN}|[\\s\\S]", program)
        width = balanced_token_width(tokens)
        return min(program, _join_tokens(tokens, width, ""), key=balance_score)
    if "\n" not in program and wrapper is wrap_grid:
        tokens = program.split()
        if not tokens:
            return program
        cell = _cell_width(tokens)
        aligned = [
            token.rjust(_span(len(token), cell) * (cell + 1) - 1) for token in tokens
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


_TOKEN_PATTERNS = _token_patterns()
