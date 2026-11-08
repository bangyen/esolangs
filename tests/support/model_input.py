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


def decimal_value(text):
    """Fold validated signed decimal digits and separators without a host cap."""
    value = 0
    for char in text.lstrip("+-"):
        if char != "_":
            value = value * 10 + unicodedata.decimal(char)
    return -value if text.startswith("-") else value
