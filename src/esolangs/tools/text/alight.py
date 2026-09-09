"""Text generator for Alight."""

__all__ = ["alight"]


def alight(text: str) -> str:
    """Return an Alight program printing ``text``.

    One ``set`` and one ``out`` per character, with the character as a
    numeric literal rather than a ``'c`` literal: ``'`` shields whatever
    follows it, so a text containing ``;``, ``"`` or ``'`` itself would
    otherwise need escaping rules the wiki never states.  A number has no
    such edge, and the program stays a single eastward line from ``begin``,
    needing no 2D layout and so no ``width``.
    """
    commands = ["begin", "var c"]
    for char in text:
        commands.append(f"set c {ord(char)}")
        commands.append("out c")
    commands.append("end")
    return ";".join(commands) + ";"
