"""Wrap generated programs to a readable width, on token boundaries.

Most generators emit one long line and most languages read a newline as
whitespace. Wrapping is token-aware: slicing every ``width`` can split a
command. It is opt-in because 2D languages read newlines as rows.

Generators declaring a width parameter lay out their own programs.
They preserve structural lines and return a width floor when the requested
width cannot fit whole tokens, statements or routing cells.

``BooleanBackend.wrap_multiline`` marks wrappers that handle structural lines.
Language-owned wrappers preserve their own token and term boundaries;
:func:`wrap_grid` right-aligns instruction cells.
``BooleanBackend.wrap`` names its wrapper; :func:`wrap_program` is the entry point.
"""

import re
from dataclasses import dataclass
from math import isqrt
from typing import TYPE_CHECKING

from esolangs._bindings import MARK, MOST_INPUTS, mark
from esolangs.generation.template import (
    InputSlot,
    TemplateLayout,
    TemplateToken,
    layout_tokens,
)
from esolangs.generation.token_balance import (
    CELL_ASPECT,
    balanced_token_width,
    rendered_side,
)

if TYPE_CHECKING:
    from esolangs.registry._backend import BooleanBackend

# 80: the conventional review/diff width, close to the repo's 88 for Python.
if TYPE_CHECKING:
    from esolangs.registry._catalog import Catalog


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


#: One input's mark run (:func:`~esolangs._bindings.mark`), one token:
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


def wrap_character_slots(layout: TemplateLayout, width: int) -> TemplateLayout:
    """Fold a single line with one-character slots and translate their offsets."""
    spans = tuple(
        (offset, offset + 1)
        for start, _ in layout.spans
        for offset in (start + start // width,)
    )
    return TemplateLayout(wrap_chars(layout.source, width), spans)


def balance_character_slots(layout: TemplateLayout) -> TemplateLayout:
    """Balance one-character slots using the same whole-token fit as text."""
    width = balanced_token_width(list(layout.source))
    fitted = wrap_character_slots(layout, width)
    return min(layout, fitted, key=lambda candidate: balance_score(candidate.source))


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


# A newline inside a bracketed literal prints; Eval also keeps each ``?x``
# conditional whole.
_BRACKET_LITERAL = r"\[[^\]]*\]|."
_EVAL_UNIT = r'"[^"]*"|\?.|.'

# FALSE ``'`` pushes the *next* character, so ``'0`` is one token and a
# newline between the two pushes 10 instead of 48. Decimal integers must
# also stay whole. Generated programs have no comments or strings.
_FALSE_COMMAND = r"'[\s\S]|[0-9]+|[\s\S]"

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

    def _template_tokens(self, layout: TemplateLayout) -> list[TemplateToken] | None:
        tokens: list[TemplateToken] = []
        for fragment in layout.fragments():
            if isinstance(fragment, InputSlot):
                tokens.append(fragment)
                continue
            literal = re.findall(self.pattern, fragment)
            if "".join(literal) != fragment:
                return None
            tokens.extend(literal)
        return tokens

    def wrap_template(self, layout: TemplateLayout, width: int) -> TemplateLayout:
        """Fold between complete tokens, including the template's slots."""
        tokens = self._template_tokens(layout)
        return layout if tokens is None else layout_tokens(tokens, width, separator="")

    def fit_template(
        self, layout: TemplateLayout, *, minimum: int = 1, maximum: int | None = None
    ) -> TemplateLayout:
        """Choose a token fit while preserving each input slot."""
        tokens = self._template_tokens(layout)
        if tokens is None:
            return layout
        width = balanced_token_width(
            [
                "x" * len(token) if isinstance(token, InputSlot) else token
                for token in tokens
            ],
            minimum=minimum,
            maximum=maximum,
        )
        return layout_tokens(tokens, width, separator="")

    def balance_template(self, layout: TemplateLayout) -> TemplateLayout:
        """Compare the original and the fitted layout."""
        fitted = self.fit_template(layout)
        return min(
            layout, fitted, key=lambda candidate: balance_score(candidate.source)
        )


_dimensional = TokenWrapper(_DIMENSIONAL_COMMAND)
_six_five = TokenWrapper(_SIX_FIVE_COMMAND)
_false = TokenWrapper(_FALSE_COMMAND)
_unlambda = TokenWrapper(_UNLAMBDA_COMMAND)
_bracket_literal = TokenWrapper(_BRACKET_LITERAL)
_quote_literal = TokenWrapper(_EVAL_UNIT)


def _backend(
    language_id: str, *, catalog: "Catalog | None" = None
) -> "BooleanBackend | None":
    """Return the registered backend for ``language_id``, if any."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)

    return next(
        (lang.backend for lang in catalog.languages.values() if lang.id == language_id),
        None,
    )


def wrap_program(
    program: str,
    language_id: str,
    width: int | None,
    *,
    catalog: "Catalog | None" = None,
) -> str:
    """Return ``program`` wrapped to ``width`` columns, if that is possible.

    ``None`` means do not wrap (the default).  A language that cannot take
    newlines, and a program already multi-line, are returned unchanged
    rather than raising; a multiline wrapper knows which lines are structural.
    """
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    if width is None or width <= 0:
        return program
    backend = _backend(language_id, catalog=catalog)
    if backend is None or backend.wrap is None:
        return program
    if "\n" in program and not backend.wrap_multiline:
        return program
    return backend.wrap(program, width)


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


def balance_program(
    program: str, language_id: str, *, catalog: "Catalog | None" = None
) -> str:
    """Balance whole-token fits and term folds; otherwise estimate source area."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    if "\n" not in program:
        balanced = _balance_line(program, language_id, catalog=catalog)
        if balanced is not None:
            return balanced
    # Token wrappers break before the width, so a neighbour can tie the side
    # with one row fewer or one column narrower.
    width = balance_width(program)
    candidates = [
        wrap_program(program, language_id, candidate, catalog=catalog)
        for candidate in (width - 1, width, width + 1)
        if candidate > 0
    ]
    return min((program, *candidates), key=balance_score)


def _balance_line(
    program: str, language_id: str, *, catalog: "Catalog | None" = None
) -> str | None:
    """Balance a one-line program by its wrapper's tokens, or None to estimate."""
    from esolangs.registry._catalog import get_catalog

    catalog = get_catalog(catalog)
    backend = _backend(language_id, catalog=catalog)
    if backend is None:
        return None
    if backend.wrap_balance is not None:
        return backend.wrap_balance(program)
    wrapper = backend.wrap
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
            program,
            wrap_program(program, language_id, width, catalog=catalog),
            key=balance_score,
        )
    return None


def balance_score(program: str) -> tuple[int, int, int]:
    """Rank rendered shapes by the side of their least square, length, then width."""
    rows = program.split("\n")
    width = max(map(len, rows), default=0)
    return rendered_side(width, len(rows)), len(program), width
