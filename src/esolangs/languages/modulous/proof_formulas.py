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


def execution_terms(_: int, program: str) -> dict[str, int]:
    """Identify the reader and count pushes that a wrapper can split."""
    commands, pushes = _layout(program)
    return {
        "D": int(commands[:2] == ["INP INT", "ADD 48"]),
        "J": int(len(commands) > 1 and commands[1] == "JMP F 3 IF 0"),
        "P": int(commands[:2] == ["INP INT", "POP"]),
        "S": pushes,
    }


def workspace_terms(n: int, program: str) -> dict[str, int]:
    """Count tokens and identify the two compact reader layouts."""
    commands, _ = _layout(program)
    direct = n == 1 and commands[:1] == ["INP INT"]
    discard = not direct and commands[:2] == ["INP INT", "POP"]
    return {"A": int(direct), "P": int(discard), "M": len(commands)}
