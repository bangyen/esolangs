r"""Wrap generated programs to a readable width, on token boundaries."""

import inspect
import re
from collections.abc import Callable

# The default width for a.
# and diff width, and matches.
# closely enough that a wrapped.
DEFAULT_WIDTH = 80


def shortest(*candidates: str) -> str:
    r"""Return the shortest of ``candidates``, preferring the earlier on a."""
    return min(candidates, key=len)


def wrap_space_delimited(program: str, width: int) -> str:
    r"""Wrap a whitespace-delimited program, never splitting a token."""
    return _join_tokens(program.split(), width, separator=" ")


def wrap_grid(program: str, width: int) -> str:
    r"""Wrap a whitespace-delimited program into a right-aligned grid."""
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
    r"""Return the cell width the bulk of ``tokens`` fits in."""
    widths = sorted({len(token) for token in tokens}, reverse=True)
    while len(widths) > 1 and widths[0] >= 2 * widths[1]:
        widths.pop(0)
    return widths[0]


def _span(length: int, cell: int) -> int:
    r"""Return how many whole cells a token of ``length`` characters needs."""
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
    r"""Wrap a program whose tokens are the matches of ``pattern``."""
    tokens = re.findall(f"{_PLACEHOLDER}|{pattern}", program)
    if "".join(tokens) != program:
        return program
    return _join_tokens(tokens, width, separator="")


def wrap_chars(program: str, width: int) -> str:
    r"""Wrap a program whose every character is its own token."""
    if "{X" not in program:
        return "\n".join(program[i : i + width] for i in range(0, len(program), width))
    tokens = re.findall(f"{_PLACEHOLDER}|[\\s\\S]", program)
    return _join_tokens(tokens, width, separator="")


def _join_tokens(tokens: list[str], width: int, separator: str) -> str:
    r"""Pack ``tokens`` into lines of at most ``width`` characters."""
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
    r"""Wrap BIO, indenting a nested program by its loop depth."""
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
    r"""Whether ``token`` opens a BIO loop."""
    return token[:2].lower() == "0i" and "{" in token


def _bio_closes(token: str) -> bool:
    r"""Whether ``token`` closes a BIO loop."""
    return token.startswith("}")


def _bio_depth(tokens: list[str]) -> int:
    r"""Return the deepest loop nesting ``tokens`` reaches."""
    depth = best = 0
    for token in tokens:
        if _bio_opens(token):
            depth += 1
            best = max(best, depth)
        elif _bio_closes(token):
            depth = max(0, depth - 1)
    return best


def _bio_indented(tokens: list[str], width: int) -> str:
    r"""Lay BIO out one loop level to a line, indented by depth."""
    lines: list[str] = []
    depth = 0
    run: list[str] = []
    # Two spaces a level, up to the.
    # of the width to pack into.
    cap = max(0, (width - width // 4) // 2)

    def flush(at: int) -> None:
        r"""Emit the pending straight run, indented for depth ``at``."""
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
    r"""Wrap 6-5, keeping each ``7n`` and the instruction it guards."""
    return wrap_tokens(program, width, _SIX_FIVE_COMMAND)


def _sophie(program: str, width: int) -> str:
    r"""Wrap Sophie, keeping each ``#<char>,`` command whole."""
    return wrap_tokens(program, width, _SOPHIE_COMMAND)


def _minifuck(program: str, width: int) -> str:
    r"""Wrap Minifuck, keeping a ``[`` run with the character it may skip."""
    return wrap_tokens(program, width, _MINIFUCK_COMMAND)


def _bitdeque(program: str, width: int) -> str:
    r"""Wrap Bitdeque, keeping each ``GOTO`` with the operand it jumps to."""
    tokens: list[str] = []
    for token in program.split():
        if tokens and tokens[-1] == "GOTO":
            tokens[-1] = f"GOTO {token}"
        else:
            tokens.append(token)
    return _join_tokens(tokens, width, separator=" ")


def _jaune(program: str, width: int) -> str:
    r"""Wrap Jaune, keeping each operand attached to the operator it feeds."""
    return wrap_tokens(program, width, _JAUNE_COMMAND)


def _bracket_literal(program: str, width: int) -> str:
    r"""Wrap 3x and Modulous, keeping a bracketed group whole."""
    return wrap_tokens(program, width, _BRACKET_LITERAL)


def _quote_literal(program: str, width: int) -> str:
    r"""Wrap Eval, keeping a double-quoted literal whole."""
    return wrap_tokens(program, width, _QUOTE_LITERAL)


def _polynomial(program: str, width: int) -> str:
    r"""Lay a Polynomial program out one signed term to a line."""
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
    r"""Break one Polynomial term across rows of at most ``width``."""
    rows = [term[i : i + width] for i in range(0, len(term), max(1, width))]
    return "\n".join(rows)


def _taglate(program: str, width: int) -> str:
    r"""Wrap Taglate's commands, leaving its queue-seed line alone."""
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
    r"""Wrap %^2^-1: fold the setter-declaration header as well as the body."""
    header, blank, body = program.partition(_PCT_HEADER_END)
    if not blank:
        return wrap_tokens(program, width, _PCT_COMMAND)
    folded = _pct_header(header.replace("\n", ""), width)
    return folded + blank + wrap_tokens(body.replace("\n", ""), width, _PCT_COMMAND)


def _pct_header(header: str, width: int) -> str:
    r"""Fold a %^2^-1 header, preferring a break between two declarations."""
    units = [unit + ";" for unit in header.split(";")]
    units[-1] = units[-1][:-1]  # the last declaration has no.
    rows: list[str] = []
    for row in _join_tokens(units, width, separator="").split("\n"):
        rows.append(row if len(row) <= width else wrap_chars(row, width))
    return "\n".join(rows)


def _qoibl(program: str, width: int) -> str:
    r"""Wrap Qoibl, folding each of its lines but keeping them apart."""
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
    r"""Whether a generator lays its own program out to a width."""
    try:
        return "width" in inspect.signature(fn).parameters
    except (TypeError, ValueError):  # pragma: no cover - builtins have no signature
        return False


def wrap_program(program: str, language_id: str, width: int | None) -> str:
    r"""Return ``program`` wrapped to ``width`` columns, if that is."""
    if width is None or width <= 0:
        return program
    if "\n" in program and language_id not in MULTILINE:
        return program
    wrapper = WRAPPERS.get(language_id)
    if wrapper is None:
        return program
    return wrapper(program, width)
