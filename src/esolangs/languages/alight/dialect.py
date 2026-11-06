"""Alight's expression-syntax and list-update dialect choices."""

EXPRESSION_SYNTAXES = ("infix", "postfix")
LIST_UPDATES = ("in_place", "copy")


def expression_syntax(value: str) -> str:
    """Validate expression notation."""
    if value not in EXPRESSION_SYNTAXES:
        raise ValueError("expression_syntax must be infix or postfix")
    return value


def list_update(value: str) -> str:
    """Validate what the three-argument ``at`` does to its list."""
    if value not in LIST_UPDATES:
        raise ValueError("list_update must be in_place or copy")
    return value
