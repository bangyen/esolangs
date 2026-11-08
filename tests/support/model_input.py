"""Independent stdin spans for reference transition models."""


def token_span(text, cursor):
    """Return the next whitespace-delimited token's start and end offsets."""
    while cursor < len(text) and text[cursor].isspace():
        cursor += 1
    start = cursor
    while cursor < len(text) and not text[cursor].isspace():
        cursor += 1
    return start, cursor
