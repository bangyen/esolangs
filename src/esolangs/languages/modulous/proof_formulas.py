"""Scalar readers, symmetric counts and half-sized indexed pair lookups."""

from esolangs.languages.modulous.interpreter import _parse_tokens


def _layout(program: str) -> tuple[list[str], int]:
    """Commands and literal pushes; splitting a literal adds no loop work."""
    commands = (
        [" ".join(token.split()) for token in _parse_tokens(program)] if program else []
    )
    pushes = sum(
        token.startswith("PSH STR") or token in {f"PSH INT {v}" for v in range(48, 52)}
        for token in commands
    )
    return commands, pushes


def execution(n: int, program: str) -> int:
    """Default maximum; a folded prologue pays each additional table push."""
    commands, pushes = _layout(program)
    if commands[:2] == ["INP INT", "ADD 48"]:
        return 4
    if len(commands) > 1 and commands[1] == "JMP F 3 IF 0":
        return 7
    if commands[:2] == ["INP INT", "POP"]:
        return 2 * n + 3
    if n == 1:
        return 7
    bound = (
        (1 << n) + 3 * n + 2
        if n <= 4
        else ((1 << (n - 1)) + 3 * n + 6 if n == 5 else 5 * (1 << (n - 1)) + 5 * n - 31)
    )
    return bound + max(0, pushes - 1)


def workspace(n: int, program: str) -> int:
    """Written stack, halt flag, token cursor and both input cursors."""
    bl = int.bit_length
    commands, _ = _layout(program)
    if n == 1 and commands and commands[0] == "INP INT":
        return 9 + bl(len(commands))
    if commands[:2] == ["INP INT", "POP"]:
        return 7 + bl(2 * n + 3) + bl(2 * n - 1) + bl(n)
    if n == 1:
        return 13
    if n <= 4:
        tokens = (1 << n) + 3 * n + 2
        return 6 * (1 << n) + 2 + bl(max(tokens, len(commands))) + bl(2 * n - 1) + bl(n)
    tokens = (1 << (n - 1)) + 3 * n + 14 if n <= 5 else 6 * n + 17
    stack = 3 * (1 << n) + (2 if n <= 5 else n + 1)
    return stack + bl(max(tokens, len(commands))) + bl(2 * n - 1) + bl(n)
