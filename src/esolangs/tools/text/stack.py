"""Stack text generators."""

__all__ = ["modulous", "the_temporary_stack"]


def modulous(text: str) -> str:
    """Build a Modulous program that outputs ``text``.

    Plain text is pushed as one ``STR`` literal and printed with ``PRT STR``;
    text containing a quote, bracket, or NUL falls back to per-character
    ``INT`` pushes so the literal is never broken.
    """
    if not text or '"' in text or "[" in text or "]" in text or "\x00" in text:
        return "".join(f"[PSH INT {ord(c)}][PRT]" for c in text) + "[END]"
    return f'[PSH STR "{text}"][PRT STR][JMP B 1 NIF 0]'


def the_temporary_stack(text: str) -> str:
    """Build a The Temporary Stack program that outputs ``text``.

    Characters are pushed as a ``*`` string literal and popped by the
    numeric mode ``o``.  Control/whitespace characters that cannot live
    inside the literal are emitted via their own ``v<value>`` token instead.
    """
    # These control/whitespace characters cannot be embedded in the ``*``
    # string literal, so they are output via their own ``v<value>`` token.
    special = (9, 10, 11, 12, 13, 28, 29, 30, 31, 32)
    k = 2 * max((ord(c) + 1 for c in text), default=0) + 2
    tokens = ["o"]
    buf: list[str] = []

    for c in text:
        inc = ord(c) + 1
        if inc in special:
            if buf:
                tokens.append("*" + "".join(buf))
                buf = []
            tokens.append(f"v{inc}")
        else:
            buf.append(chr(inc))

    if buf:
        tokens.append("*" + "".join(buf))
    tokens.append(f"v{k}")

    return " ".join(tokens)
