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
- ROTfuck treats a newline as a comment, yet still cannot be wrapped: every
  executed command rotates the program, and brackets are matched by seeking
  through the *rotated* text, so a character's position is semantic.
  Inserting newlines shifts those positions and breaks bracket matching at
  any width (verified: it fails at 40, 80, and 120 alike).

:data:`WRAPPERS` maps a language id to the wrapper it needs; a language
absent from it is not wrapped.  :func:`wrap_program` is the entry point the
generators and the public API call.
"""

import re

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
_BIO_TOKEN = r"[01][oOiI][xXyYzZ]|[{}]| "

# Brainfuck-family single-character commands, and the languages that
# extend them with a digit argument (Dimensional's ``>0``/``<0``).
_DIMENSIONAL_TOKEN = r"[<>]\d+|."


def _bio(program: str, width: int) -> str:
    # The boolean BIO generator separates commands with spaces while the text
    # one does not, so a space is one of BIO's tokens here.  A line must not
    # start with that separator, so break *before* the command it precedes:
    # attaching each space to the following command makes the pair a single
    # unbreakable token and keeps the newline where a space already was.
    tokens = re.findall(_BIO_TOKEN, program)
    if "".join(tokens) != program:
        return program
    merged: list[str] = []
    for token in tokens:
        if token == " " and merged:
            merged[-1] += token
        else:
            merged.append(token)
    wrapped = _join_tokens(merged, width, separator="")
    # A break after a command leaves its trailing separator at the end of the
    # line; the newline separates the commands just as well, so drop it.
    return "\n".join(line.rstrip(" ") for line in wrapped.split("\n"))


def _dimensional(program: str, width: int) -> str:
    return wrap_tokens(program, width, _DIMENSIONAL_TOKEN)


# Language id -> the wrapper that language needs.  A language absent here
# is never wrapped: either its newlines are semantic (the 2D grid
# languages), it rejects them outright (NoComment), or its own execution
# model makes character position meaningful (ROTfuck).  See the module
# docstring for why each exclusion is an exclusion.
WRAPPERS = {
    "addsubjump": wrap_space_delimited,
    "decleq": wrap_space_delimited,
    "sbleq": wrap_space_delimited,
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
    "modulous": wrap_chars,
    "forth": wrap_chars,
    "eval": wrap_chars,
    "sophie": wrap_chars,
    "myscript": wrap_chars,
    "three_x": wrap_chars,
}


def wrap_program(program: str, language_id: str, width: int | None) -> str:
    """Return ``program`` wrapped to ``width`` columns, if that is possible.

    ``width`` of ``None`` means "do not wrap" and returns the program
    unchanged, which is the default everywhere: wrapping is opt-in, so the
    generators keep producing exactly what they produced before unless a
    caller asks for a width.

    A language that cannot take newlines is returned unchanged rather than
    raising, so a caller can pass one width across every language without
    special-casing the handful of exclusions.  Likewise a program that is
    already multi-line (the 2D and line-oriented languages) is left alone.
    """
    if width is None or width <= 0 or "\n" in program:
        return program
    wrapper = WRAPPERS.get(language_id)
    if wrapper is None:
        return program
    return wrapper(program, width)
