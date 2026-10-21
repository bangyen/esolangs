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
from dataclasses import dataclass
from math import isqrt
from typing import TYPE_CHECKING, Any

from esolangs.generation.helpers import MARK, MOST_INPUTS, mark
from esolangs.generation.token_balance import (
    CELL_ASPECT,
    balanced_token_width,
    rendered_side,
)

if TYPE_CHECKING:
    from esolangs.registry import Language

# 80: the conventional review/diff width, close to the repo's 88 for Python.
DEFAULT_WIDTH = 80


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


def _tokens(program: str, pattern: str) -> list[str]:
    """Split ``program`` into tokens, trying a template run ahead of ``pattern``."""
    return re.findall(f"{_RUN}|{pattern}", program)


_MARK_PATTERN = re.compile(f"[{chr(MARK)}-{chr(MARK + MOST_INPUTS - 1)}]")


def wrap_tokens(program: str, width: int, pattern: str) -> str:
    """Wrap a program whose tokens are the matches of ``pattern``.

    ``pattern`` must tile the program exactly; one that does not is returned
    unwrapped.  A :data:`_RUN` is tried ahead of ``pattern``.
    """
    tokens = _tokens(program, pattern)
    if "".join(tokens) != program:
        return program
    return _join_tokens(tokens, width, separator="")


def wrap_chars(program: str, width: int) -> str:
    """Wrap a program whose every character is its own token.

    Any position is a legal break, except inside a template's :data:`_RUN`.
    """
    if not _MARK_PATTERN.search(program):
        return "\n".join(program[i : i + width] for i in range(0, len(program), width))
    return _join_tokens(_tokens(program, r"[\s\S]"), width, separator="")


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
# character, not ``[0-9A-Z]`` (``_operand("7\n")`` is -45).  ``7n`` skips the
# next *token*, a newline included (``706A`` leaves cell 0, ``70\n6A`` cell
# 6), so it swallows the instruction it guards, operand included; ``8n``
# counts ``4`` markers and needs no pairing.
_SIX_FIVE_COMMAND = r"7[\s\S](?:[78][\s\S]|[\s\S])|8[\s\S]|[\s\S]"


# Minifuck ``[`` skips the next character (``ind + 2``), so a newline
# there is what gets skipped; consecutive ``[`` chain, so the whole run
# stays with the character after it, or with the input run after it.
_MINIFUCK_COMMAND = rf"\[+(?:{_RUN}|[\s\S])|[\s\S]"


# A newline inside a bracketed literal prints; Eval also keeps each ``?x``
# conditional whole.
_BRACKET_LITERAL = r"\[[^\]]*\]|."
_EVAL_UNIT = r'"[^"]*"|\?.|.'

# FALSE ``'`` pushes the *next* character, so ``'0`` is one token and a
# newline between the two pushes 10 instead of 48.  A ``{comment}`` or
# ``"string"`` would be a third unit; no generated program has either.
_FALSE_COMMAND = r"'[\s\S]|[\s\S]"

# Unlambda ``.x`` and ``?x`` take the next character too: a break inside
# ``.0`` prints a newline, and one inside ``?0`` asks about one.
_UNLAMBDA_COMMAND = r"[.?][\s\S]|[\s\S]"


@dataclass(frozen=True)
class TokenWrapper:
    """A wrapper that breaks only between matches of ``pattern``.

    :func:`balance_program` fits the same tokens, reading ``pattern`` off it.
    """

    pattern: str

    def __call__(self, program: str, width: int) -> str:
        """Wrap ``program`` to ``width`` between tokens."""
        return wrap_tokens(program, width, self.pattern)


_dimensional = TokenWrapper(_DIMENSIONAL_COMMAND)
_six_five = TokenWrapper(_SIX_FIVE_COMMAND)
_false = TokenWrapper(_FALSE_COMMAND)
_unlambda = TokenWrapper(_UNLAMBDA_COMMAND)
_bracket_literal = TokenWrapper(_BRACKET_LITERAL)
_quote_literal = TokenWrapper(_EVAL_UNIT)


def _minifuck(program: str, width: int) -> str:
    """Wrap Minifuck, keeping a ``[`` run with the character it may skip.

    ``[`` skips two *characters*, a newline included; a run chains, so in
    ``[[x`` a break before ``x`` is unsafe.
    """
    tokens = _tokens(program, _MINIFUCK_COMMAND)
    floor = max(map(len, tokens), default=0)
    if "\n" in program and max(map(len, program.split("\n"))) <= max(width, floor):
        return program
    return _join_tokens(tokens, width, separator="")


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


def _language(language_id: str) -> "Language | None":
    """Return the registered language with ``language_id``, if any."""
    from esolangs.registry import LANGUAGES

    return next((lang for lang in LANGUAGES.values() if lang.id == language_id), None)


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
    lang = _language(language_id)
    if lang is None or lang.wrap is None:
        return program
    if "\n" in program and not lang.wrap_multiline:
        return program
    return lang.wrap(program, width)


def balance_width(program: str) -> int:
    """Return the best character-fold width for the default rendered area.

    The least side S with CELL_ASPECT * ceil(area/S) <= S, then the fewest
    columns keeping its ceil(area/S) rows: exact for a pure character fold.
    """
    rows = program.split("\n")
    area = max(1, sum(map(len, rows)))
    side = isqrt(CELL_ASPECT * area - 1) + 1
    while CELL_ASPECT * -(-area // side) > side:
        side += 1
    return -(-area // -(-area // side))


def _token_fit(program: str, tokens: list[str], separator: str = "") -> str:
    """Return ``program`` or its tokens at their balanced width, the squarer."""
    width = balanced_token_width(tokens, separator)
    return min(program, _join_tokens(tokens, width, separator), key=balance_score)


def balance_program(program: str, language_id: str) -> str:
    """Balance whole-token fits and term folds; otherwise estimate source area."""
    if "\n" not in program:
        balanced = _balance_line(program, language_id)
        if balanced is not None:
            return balanced
    # Token wrappers break before the width, so a neighbour can tie the side
    # with one row fewer or one column narrower.
    width = balance_width(program)
    candidates = [
        wrap_program(program, language_id, candidate)
        for candidate in (width - 1, width, width + 1)
        if candidate > 0
    ]
    return min((program, *candidates), key=balance_score)


def _balance_line(program: str, language_id: str) -> str | None:
    """Balance a one-line program by its wrapper's tokens, or None to estimate."""
    lang = _language(language_id)
    if lang is None:
        return None
    if lang.wrap_balance is not None:
        return lang.wrap_balance(program)
    wrapper = lang.wrap
    if wrapper is wrap_space_delimited:
        return _token_fit(program, program.split(), " ")
    if isinstance(wrapper, TokenWrapper):
        return _token_fit(program, _tokens(program, wrapper.pattern))
    if wrapper is wrap_chars and _MARK_PATTERN.search(program):
        return _token_fit(program, _tokens(program, r"[\s\S]"))
    if wrapper is wrap_grid:
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
    return None


def balance_score(program: str) -> tuple[int, int, int]:
    """Rank rendered shapes by the side of their least square, length, then width."""
    rows = program.split("\n")
    width = max(map(len, rows), default=0)
    return rendered_side(width, len(rows)), len(program), width
