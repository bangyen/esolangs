"""Independent stdin spans for reference transition models."""

import unicodedata


def token_span(text, cursor):
    """Return the next whitespace-delimited token's start and end offsets."""
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    start = cursor
    while cursor < len(text) and not text[cursor].isspace():
        cursor += 1
    return start, cursor


def line_span(text, cursor):
    """Return a line without its terminator and the next offset."""
    end = text.find("\n", cursor)
    stop = len(text) if end < 0 else end + 1
    return text[cursor:stop].removesuffix("\r\n").removesuffix("\n"), stop


def decimal_value(text):
    """Fold validated signed decimal digits and separators without a host cap."""
    value = 0
    for char in text.lstrip("+-"):
        if char != "_":
            value = value * 10 + unicodedata.decimal(char)
    return -value if text.startswith("-") else value


def integer_rejection(token):
    """Predict the numeric port's bad-token diagnostic."""
    return (
        "ArgumentError",
        f"input must be an integer, got {token!r}",
        ("hint: supply a whitespace-separated decimal integer, for example 42",),
    )


def rejected_integer(rows, stdin):
    start, end = token_span(stdin, rows[-2][-1])
    return integer_rejection(stdin[start:end])


def rejected_integer_syntax(rows, stdin, *, base=10):
    """Predict the ordinary ValueError from a rejected integer token."""
    if len(rows) < 2 or rows[-2][-1] == rows[-1][-1]:
        return None
    start, end = token_span(stdin, rows[-2][-1])
    return (
        "ValueError",
        f"invalid literal for int() with base {base}: " + repr(stdin[start:end])[:200],
        (),
    )


def rejected_fraction_syntax(_rows, _stdin):
    return (
        "ValueError",
        "input must be an integer or a fraction",
        (
            "hint: supply a decimal integer or a fraction with nonzero denominator, "
            "for example 3/2",
        ),
    )


def matching_delimiter(tokens, opening, closing):
    """Return tokens consumed through the matching closer, or None."""
    depth = 1
    for span, token in enumerate(tokens, 1):
        depth += (token == opening) - (token == closing)
        if depth == 0:
            return span
    return None
