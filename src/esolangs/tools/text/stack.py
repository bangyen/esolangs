"""Stack text generators."""

__all__ = ["modulous"]


def modulous(text: str) -> str:
    """Build a Modulous program that outputs ``text``.

    Plain text is pushed as one ``STR`` literal and printed with ``PRT STR``;
    text containing a quote, bracket, or NUL falls back to per-character
    ``INT`` pushes so the literal is never broken.
    """
    if not text or '"' in text or "[" in text or "]" in text or "\x00" in text:
        return "".join(f"[PSH INT {ord(c)}][PRT]" for c in text) + "[END]"
    return f'[PSH STR "{text}"][PRT STR][JMP B 1 NIF 0]'
